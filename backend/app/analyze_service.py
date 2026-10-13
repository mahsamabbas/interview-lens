import json

from pydantic import ValidationError

from app import config
from app.models import CandidateReport, GapItem, HiringReport
from app.ollama_client import chat_json


class AnalyzeError(Exception):
    pass


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


def _build_prompt(jd: str, transcript: str) -> str:
    schema = {
        "candidate": {
            "scores": {
                k: {"score": "int 0-100", "rationale": "str"}
                for k in ("jd_match", "answer_depth", "communication", "structure", "overall")
            },
            "summary": "str",
            "strengths": [{"point": "str", "evidence_quote": "verbatim from transcript"}],
            "improvements": [
                {"point": "str", "evidence_quote": "verbatim from transcript", "tip": "str"}
            ],
            "question_notes": [
                {
                    "topic_or_question": "str",
                    "note": "str",
                    "evidence_quote": "verbatim from transcript",
                }
            ],
            "readiness_note": "str",
            "unknowns": ["str"],
        },
        "hiring": {
            "scores": "same shape as candidate.scores",
            "recommendation": "pass | borderline | no",
            "hire_confidence": "int 0-100",
            "fit_summary": "str",
            "skill_evidence": [{"skill": "str", "evidence_quote": "verbatim from transcript"}],
            "gaps": [{"skill_or_requirement": "str", "note": "str"}],
            "red_flags": [{"note": "str", "evidence_quote": "verbatim from transcript"}],
            "follow_up_questions": ["str"],
            "unknowns": ["str"],
            "disclaimer": "str",
        },
    }
    return (
        "You are an interview analyst. Compare the interview transcript to the job description "
        "and produce two reports as ONE JSON object with keys \"candidate\" and \"hiring\".\n\n"
        "Rules:\n"
        "- Every evidence_quote MUST be copied verbatim from the transcript. Use quotes only "
        "from the transcript; do not paraphrase or invent quotes.\n"
        "- If a required skill has no evidence in the transcript, list it under gaps or "
        "unknowns. Never invent evidence. Never invent a PASS: recommend \"pass\" only when "
        "the transcript clearly supports it.\n"
        "- Be honest and concise. Output JSON only, no commentary.\n\n"
        f"JSON shape:\n{json.dumps(schema, indent=2)}\n\n"
        f"=== JOB DESCRIPTION ===\n{jd.strip()}\n\n"
        f"=== TRANSCRIPT ===\n{transcript}\n"
    )


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

    prompt = _build_prompt(jd, transcript)
    last_err: Exception | None = None
    for _ in range(2):
        try:
            data = chat_json(prompt)
            cand = CandidateReport.model_validate(data["candidate"])
            hire = HiringReport.model_validate(
                {"disclaimer": config.HIRING_DISCLAIMER, **data["hiring"]}
            )
        except (ValidationError, KeyError, TypeError, ValueError) as e:
            last_err = e
            continue
        except Exception as e:  # LLM/transport failure
            raise AnalyzeError(f"LLM call failed: {e}") from e
        return _filter_evidence(cand, hire, transcript)
    raise AnalyzeError(f"LLM returned invalid report JSON after retry: {last_err}")
