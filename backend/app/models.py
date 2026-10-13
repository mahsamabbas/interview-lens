from typing import Literal

from pydantic import BaseModel, Field

Speaker = Literal["interviewer", "candidate", "unknown"]
Recommendation = Literal["pass", "borderline", "no"]
JobStatus = Literal[
    "queued",
    "transcribing",
    "diarizing",
    "ready",
    "analyzing",
    "done",
    "error",
]
SourceType = Literal["sample_video", "upload", "paste"]
JobKind = Literal["transcribe", "analyze"]


class ScoreItem(BaseModel):
    score: int = Field(ge=0, le=100)
    rationale: str


class ScoreBlock(BaseModel):
    jd_match: ScoreItem
    answer_depth: ScoreItem
    communication: ScoreItem
    structure: ScoreItem
    overall: ScoreItem


class StrengthItem(BaseModel):
    point: str
    evidence_quote: str


class ImprovementItem(BaseModel):
    point: str
    evidence_quote: str
    tip: str


class QuestionNote(BaseModel):
    topic_or_question: str
    note: str
    evidence_quote: str


class CandidateReport(BaseModel):
    scores: ScoreBlock
    summary: str
    strengths: list[StrengthItem]
    improvements: list[ImprovementItem]
    question_notes: list[QuestionNote]
    readiness_note: str
    unknowns: list[str]


class SkillEvidence(BaseModel):
    skill: str
    evidence_quote: str


class GapItem(BaseModel):
    skill_or_requirement: str
    note: str


class RedFlag(BaseModel):
    note: str
    evidence_quote: str


class HiringReport(BaseModel):
    scores: ScoreBlock
    recommendation: Recommendation
    hire_confidence: int = Field(ge=0, le=100)
    fit_summary: str
    skill_evidence: list[SkillEvidence]
    gaps: list[GapItem]
    red_flags: list[RedFlag]
    follow_up_questions: list[str]
    unknowns: list[str]
    disclaimer: str


class CreateSessionIn(BaseModel):
    title: str


class CreateSessionOut(BaseModel):
    id: str


class JdIn(BaseModel):
    jd_text: str


class PasteIn(BaseModel):
    text: str


class SegmentIn(BaseModel):
    idx: int
    start_ms: int = 0
    end_ms: int = 0
    speaker: Speaker
    text: str


class TranscriptPatchIn(BaseModel):
    segments: list[SegmentIn]


class SegmentOut(BaseModel):
    id: str
    session_id: str
    idx: int
    start_ms: int
    end_ms: int
    speaker: Speaker
    text: str


class SessionSummaryOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    source_type: SourceType | None = None


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    status: str
    jd_text: str
    source_type: SourceType | None = None
    media_path: str | None = None
    segments: list[SegmentOut] = Field(default_factory=list)


class JobOut(BaseModel):
    id: str
    session_id: str
    kind: JobKind
    status: JobStatus
    error_message: str | None = None
    created_at: str
    updated_at: str


class JobCreatedOut(BaseModel):
    job_id: str


class ReportsOut(BaseModel):
    candidate: CandidateReport
    hiring: HiringReport
