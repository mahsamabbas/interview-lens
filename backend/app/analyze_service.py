import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app import config
from app.models import (
    CandidateReport,
    GapItem,
    HiringReport,
    Recommendation,
    ScoreBlock,
)
from app.ollama_client import chat_json

# Keep prompts inside a size 7B models can finish as valid JSON quickly.
_MAX_TRANSCRIPT_CHARS = 8_000
_MAX_JD_CHARS = 2_500


class AnalyzeError(Exception):
    pass


class _LLMHiring(BaseModel):
    """Hiring fields the model must produce (disclaimer is forced server-side)."""

    scores: ScoreBlock
    recommendation: Recommendation
    hire_confidence: int = Field(ge=0, le=100)
    fit_summary: str
    skill_evidence: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    red_flags: list[dict[str, Any]] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class _LLMDual(BaseModel):
    candidate: CandidateReport
    hiring: _LLMHiring


def evidence_allowed(quote: str, transcript_blob: str) -> bool:
    """Case-insensitive substring check of a quote against the full transcript."""
    q = " ".join((quote or "").split()).lower()
    if not q:
        return False
    return q in " ".join(transcript_blob.split()).lower()


def _transcript_text(segments: list[dict]) -> str:
    lines = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{(s.get('speaker') or 'unknown').capitalize()}: {text}")
    return "\n".join(lines)


def _truncate_transcript(transcript: str) -> str:
    if len(transcript) <= _MAX_TRANSCRIPT_CHARS:
        return transcript
    half = _MAX_TRANSCRIPT_CHARS // 2
    return (
        transcript[:half]
        + "\n\n[... middle of transcript omitted for length ...]\n\n"
        + transcript[-half:]
    )


def _truncate_jd(jd: str) -> str:
    jd = (jd or "").strip()
    if len(jd) <= _MAX_JD_CHARS:
        return jd
    return jd[:_MAX_JD_CHARS] + "\n\n[... JD truncated for length ...]"


def _score_schema() -> dict:
    return {
        "type": "object",
        "required": ["score", "rationale"],
        "properties": {
            "score": {"type": "integer"},
            "rationale": {"type": "string"},
        },
    }


def _dual_format_schema() -> dict:
    """Ollama structured-output schema (hiring.disclaimer omitted — set by server)."""
    score_block = {
        "type": "object",
        "required": [
            "jd_match",
            "answer_depth",
            "communication",
            "structure",
            "overall",
        ],
        "properties": {
            k: _score_schema()
            for k in (
                "jd_match",
                "answer_depth",
                "communication",
                "structure",
                "overall",
            )
        },
    }
    return {
        "type": "object",
        "required": ["candidate", "hiring"],
        "properties": {
            "candidate": {
                "type": "object",
                "required": [
                    "scores",
                    "summary",
                    "strengths",
                    "improvements",
                    "question_notes",
                    "readiness_note",
                    "unknowns",
                ],
                "properties": {
                    "scores": score_block,
                    "summary": {"type": "string"},
                    "strengths": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["point", "evidence_quote"],
                            "properties": {
                                "point": {"type": "string"},
                                "evidence_quote": {"type": "string"},
                            },
                        },
                    },
                    "improvements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["point", "evidence_quote", "tip"],
                            "properties": {
                                "point": {"type": "string"},
                                "evidence_quote": {"type": "string"},
                                "tip": {"type": "string"},
                            },
                        },
                    },
                    "question_notes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["topic_or_question", "note", "evidence_quote"],
                            "properties": {
                                "topic_or_question": {"type": "string"},
                                "note": {"type": "string"},
                                "evidence_quote": {"type": "string"},
                            },
                        },
                    },
                    "readiness_note": {"type": "string"},
                    "unknowns": {"type": "array", "items": {"type": "string"}},
                },
            },
            "hiring": {
                "type": "object",
                "required": [
                    "scores",
                    "recommendation",
                    "hire_confidence",
                    "fit_summary",
                    "skill_evidence",
                    "gaps",
                    "red_flags",
                    "follow_up_questions",
                    "unknowns",
                ],
                "properties": {
                    "scores": score_block,
                    "recommendation": {
                        "type": "string",
                        "enum": ["pass", "borderline", "no"],
                    },
                    "hire_confidence": {"type": "integer"},
                    "fit_summary": {"type": "string"},
                    "skill_evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["skill", "evidence_quote"],
                            "properties": {
                                "skill": {"type": "string"},
                                "evidence_quote": {"type": "string"},
                            },
                        },
                    },
                    "gaps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["skill_or_requirement", "note"],
                            "properties": {
                                "skill_or_requirement": {"type": "string"},
                                "note": {"type": "string"},
                            },
                        },
                    },
                    "red_flags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["note", "evidence_quote"],
                            "properties": {
                                "note": {"type": "string"},
                                "evidence_quote": {"type": "string"},
                            },
                        },
                    },
                    "follow_up_questions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "unknowns": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }


def _build_prompt(jd: str, transcript: str) -> str:
    return (
        "Analyze this interview. Return ONE JSON object with exactly two keys: "
        '"candidate" and "hiring".\n\n'
        "hiring MUST include ALL of these keys (use [] for empty lists): "
        "scores, recommendation (pass|borderline|no), hire_confidence (0-100), "
        "fit_summary, skill_evidence, gaps, red_flags, follow_up_questions, unknowns.\n"
        "Do NOT put a disclaimer field in hiring.\n"
        "candidate MUST include: scores, summary, strengths, improvements, "
        "question_notes, readiness_note, unknowns.\n"
        "scores needs jd_match, answer_depth, communication, structure, overall — "
        "each {score:int, rationale:str}.\n"
        "evidence_quote values must be short verbatim snippets from the transcript "
        "(or empty string if none). Never invent skills or a pass without evidence.\n\n"
        f"=== JOB DESCRIPTION ===\n{_truncate_jd(jd)}\n\n"
        f"=== TRANSCRIPT ===\n{transcript}\n"
    )


def _build_repair_prompt(jd: str, transcript: str, bad: dict, err: str) -> str:
    return (
        "Your previous JSON was invalid for our schema.\n"
        f"Validation error:\n{err}\n\n"
        "Previous JSON:\n"
        f"{json.dumps(bad)[:2500]}\n\n"
        "Return a COMPLETE corrected JSON object with both candidate and hiring. "
        "hiring must include recommendation, hire_confidence, fit_summary, scores, "
        "skill_evidence, gaps, red_flags, follow_up_questions, unknowns "
        "(use [] where empty). No disclaimer field. Keep text concise.\n\n"
        f"=== JOB DESCRIPTION ===\n{_truncate_jd(jd)}\n\n"
        f"=== TRANSCRIPT ===\n{transcript}\n"
    )


def _normalize_payload(data: dict) -> dict:
    """Pull candidate/hiring out of common LLM wrapping mistakes."""
    if not isinstance(data, dict):
        raise ValueError("payload is not an object")
    if "candidate" in data and "hiring" in data:
        return data
    # Sometimes models nest under "reports" / "result"
    for key in ("reports", "result", "data", "output"):
        inner = data.get(key)
        if isinstance(inner, dict) and "candidate" in inner and "hiring" in inner:
            return inner
    raise ValueError("JSON missing top-level candidate and hiring keys")


def _parse_reports(data: dict) -> tuple[CandidateReport, HiringReport]:
    data = _normalize_payload(data)
    dual = _LLMDual.model_validate(data)
    hire = HiringReport.model_validate(
        {
            **dual.hiring.model_dump(),
            "disclaimer": config.HIRING_DISCLAIMER,
        }
    )
    return dual.candidate, hire


def _filter_evidence(
    cand: CandidateReport, hire: HiringReport, blob: str
) -> tuple[CandidateReport, HiringReport]:
    ok = lambda q: evidence_allowed(q, blob)  # noqa: E731
    cand.strengths = [x for x in cand.strengths if ok(x.evidence_quote)]
    cand.improvements = [x for x in cand.improvements if ok(x.evidence_quote)]
    cand.question_notes = [x for x in cand.question_notes if ok(x.evidence_quote)]
    kept, dropped = [], []
    for x in hire.skill_evidence:
        (kept if ok(x.evidence_quote) else dropped).append(x)
    hire.skill_evidence = kept
    existing = {g.skill_or_requirement.lower() for g in hire.gaps}
    for x in dropped:
        if x.skill.lower() not in existing:
            hire.gaps.append(
                GapItem(
                    skill_or_requirement=x.skill,
                    note="No supporting evidence found in transcript.",
                )
            )
            existing.add(x.skill.lower())
    hire.red_flags = [x for x in hire.red_flags if ok(x.evidence_quote)]
    if hire.recommendation == "pass" and (not hire.skill_evidence or dropped):
        hire.recommendation = "borderline"
        hire.hire_confidence = min(hire.hire_confidence, 60)
    hire.disclaimer = config.HIRING_DISCLAIMER
    return cand, hire


def analyze_interview(jd: str, segments: list[dict]) -> tuple[CandidateReport, HiringReport]:
    if len((jd or "").strip()) < config.MIN_JD_CHARS:
        raise AnalyzeError(
            f"Job description must be at least {config.MIN_JD_CHARS} characters."
        )
    transcript = _transcript_text(segments or [])
    if not transcript:
        raise AnalyzeError("Cannot analyze: transcript is empty.")
    transcript = _truncate_transcript(transcript)

    schema = _dual_format_schema()
    prompt = _build_prompt(jd, transcript)
    last_err: Exception | None = None
    last_data: dict | None = None

    for attempt in range(2):
        try:
            if attempt == 0:
                data = chat_json(prompt, format_schema=schema)
            else:
                data = chat_json(
                    _build_repair_prompt(jd, transcript, last_data or {}, str(last_err)),
                    format_schema=schema,
                )
            last_data = data
            cand, hire = _parse_reports(data)
        except (ValidationError, KeyError, TypeError, ValueError) as e:
            last_err = e
            continue
        except Exception as e:  # LLM/transport failure
            raise AnalyzeError(f"LLM call failed: {e}") from e
        return _filter_evidence(cand, hire, transcript)

    raise AnalyzeError(f"LLM returned invalid report JSON after retry: {last_err}")
