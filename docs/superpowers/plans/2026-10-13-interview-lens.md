# InterviewLens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build InterviewLens — a local two-step interview studio that turns JD + video/audio (or pasted transcript) into editable diarized segments, then dual evidence-backed reports (candidate feedback + hiring PASS/borderline/NO) via Whisper, pyannote, Ollama, SQLite, and a unique React UI.

**Architecture:** React (Vite) owns the InterviewLens stepper UI (Setup → Transcript → Reports). FastAPI owns SQLite, media on disk, background-style jobs (in-process), faster-whisper + pyannote, and Ollama structured JSON analysis. Browser never calls Ollama or Whisper. Paste path works without STT.

**Tech Stack:** React 19, Vite, TypeScript, Tailwind CSS v4, FastAPI, Pydantic v2, SQLite (`sqlite3`), httpx, faster-whisper, pyannote.audio (HF token), Ollama `qwen2.5:7b`, pytest, Vitest (optional helpers), Docker Compose.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-10-13-interview-lens-design.md`
- Chat model default: `qwen2.5:7b` via `OLLAMA_CHAT_MODEL`
- Ports: frontend `3004`, API `8004`, Ollama `11434`
- Brand: **InterviewLens** — display **Sora**, UI **Manrope**; ink `#0B1220`, mint `#3EE0B7`, amber `#F5B942`
- No cloud LLM/STT; no Zoom bots; no ATS; assistive disclaimer on hiring report
- Evidence quotes must come from transcript; never invent skills or force PASS
- Job poll statuses: `queued` | `transcribing` | `diarizing` | `ready` | `analyzing` | `done` | `error`
- Speakers: `interviewer` | `candidate` | `unknown`
- Tests mock Ollama, Whisper, and pyannote — no live network in pytest
- Git author: **mahsamabbas** `<6658043+mahsamabbas@users.noreply.github.com>`; strip Cursor co-author (prefer `commit-tree` or one-shot `-c user.name/email`)
- Work at repo root `interview-lens/`

## File map

| Path | Responsibility |
| --- | --- |
| `backend/app/config.py` | Env, paths, CORS, model names, limits |
| `backend/app/validation.py` | JD text + media upload validation |
| `backend/app/db.py` | SQLite connect, schema, helpers |
| `backend/app/models.py` | Pydantic API + report schemas |
| `backend/app/transcript_parse.py` | Paste → segments (labeled lines) |
| `backend/app/ollama_client.py` | Chat JSON + `ollama_ok()` |
| `backend/app/stt_service.py` | Whisper + pyannote → segments (injectable) |
| `backend/app/analyze_service.py` | JD + segments → dual reports |
| `backend/app/jobs.py` | Create/update/run jobs |
| `backend/app/main.py` | FastAPI routes + CORS + lifespan |
| `backend/data/sample_jd.md` | Demo job description |
| `backend/data/sample_transcript.md` | Labeled sample interview |
| `backend/data/sample_interview.wav` | Short bundled audio (or generated in setup) |
| `backend/tests/*` | pytest |
| `frontend/src/styles.css` | Tokens, atmosphere, motion |
| `frontend/src/lib/api.ts` | HTTP client |
| `frontend/src/lib/jobCopy.ts` | Progress strings (Vitest) |
| `frontend/src/components/*` | Stepper, Home, Setup, Transcript, Reports |
| `frontend/src/App.tsx` | Session routing / step state |
| `docker-compose.yml` | frontend + backend; Ollama on host |
| `README.md` | Setup, ports, HF token, tests, limits |

---

### Task 1: Backend scaffold, config, validation, sample text assets

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/validation.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_validation.py`
- Create: `backend/data/sample_jd.md`
- Create: `backend/data/sample_transcript.md`

**Interfaces:**
- Produces: `validate_jd_text(text: str) -> str` raises `ValidationError`
- Produces: `validate_media_filename(filename: str) -> str` (extension check)
- Produces: `MIN_JD_CHARS=40`, `MAX_JD_CHARS=20000`, `ALLOWED_MEDIA={".wav",".mp3",".m4a",".webm",".mp4"}`, `ALLOWED_JD_EXT={".txt",".md"}`

- [ ] **Step 1: Write `backend/requirements.txt`**

```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9
python-dotenv>=1.0.0
pydantic>=2.0.0
httpx>=0.27.0
pytest>=8.0.0
faster-whisper>=1.0.0
# pyannote is heavy — pin in README; tests mock STT so CI can omit GPU deps if needed
torch>=2.0.0
pyannote.audio>=3.1.0
```

- [ ] **Step 2: Write failing validation tests**

```python
# backend/tests/test_validation.py
import pytest

from app.validation import ValidationError, validate_jd_text, validate_media_filename


def test_jd_rejects_empty():
    with pytest.raises(ValidationError, match="at least"):
        validate_jd_text("short")


def test_jd_accepts_long_enough():
    text = "Engineer role. " + ("Need Python. " * 10)
    assert validate_jd_text(text) == text.strip()


def test_media_rejects_exe():
    with pytest.raises(ValidationError, match="extension"):
        validate_media_filename("virus.exe")


def test_media_accepts_wav():
    assert validate_media_filename("interview.WAV") == ".wav"
```

- [ ] **Step 3: Run — expect fail**

```bash
cd backend && python3.12 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn python-multipart python-dotenv pydantic httpx pytest
PYTHONPATH=. pytest tests/test_validation.py -v
```

Expected: FAIL (module not found / import error)

- [ ] **Step 4: Implement `config.py` + `validation.py` + samples + `.env.example`**

```python
# backend/app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")

DATA_DIR = BACKEND_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLE_JD_PATH = DATA_DIR / "sample_jd.md"
SAMPLE_TRANSCRIPT_PATH = DATA_DIR / "sample_transcript.md"
SAMPLE_MEDIA_PATH = DATA_DIR / "sample_interview.wav"
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(DATA_DIR / "interviewlens.db")))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:7b")
HF_TOKEN = os.getenv("HF_TOKEN", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
MIN_JD_CHARS = 40
MAX_JD_CHARS = 20_000
ALLOWED_MEDIA = {".wav", ".mp3", ".m4a", ".webm", ".mp4"}
ALLOWED_JD_EXT = {".txt", ".md"}
HIRING_DISCLAIMER = (
    "InterviewLens is an assistive tool only. Final hiring decisions must be made by a human."
)
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3004,http://127.0.0.1:3004",
    ).split(",")
    if o.strip()
]
```

```python
# backend/app/validation.py
from pathlib import Path
from app import config


class ValidationError(Exception):
    pass


def validate_jd_text(text: str) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) < config.MIN_JD_CHARS:
        raise ValidationError(f"Job description must be at least {config.MIN_JD_CHARS} characters.")
    if len(cleaned) > config.MAX_JD_CHARS:
        raise ValidationError(f"Job description must be at most {config.MAX_JD_CHARS} characters.")
    return cleaned


def validate_media_filename(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in config.ALLOWED_MEDIA:
        raise ValidationError("Unsupported media extension. Use wav, mp3, m4a, webm, or mp4.")
    return ext
```

Sample JD: short Backend Engineer JD (Python, APIs, SQL).  
Sample transcript: 8–12 labeled turns (`Interviewer:` / `Candidate:`) — candidate strong on Python, weak/missing on system design.

- [ ] **Step 5: Run tests — expect pass**

```bash
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest tests/test_validation.py -v
```

- [ ] **Step 6: Commit**

```bash
# author mahsamabbas only — use commit-tree if Cursor injects co-author
git add backend/
git commit -m "Add InterviewLens backend scaffold, validation, and sample text."
```

---

### Task 2: SQLite schema + Pydantic models

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Create: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `get_connection()`, `init_db()`, `create_session(title: str) -> str`, CRUD helpers used by later routes
- Produces models: `ScoreBlock`, `CandidateReport`, `HiringReport`, `SegmentIn`, `SegmentOut`, `SessionOut`, `JobOut`, `ReportsOut`

- [ ] **Step 1: Write failing db test**

```python
# backend/tests/test_db.py
from pathlib import Path
import app.config as config
from app import db


def test_init_and_create_session(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "t.db")
    db.init_db()
    sid = db.create_session("Demo")
    row = db.get_session(sid)
    assert row["title"] == "Demo"
    assert row["status"] == "draft"
```

- [ ] **Step 2: Run — expect fail**

```bash
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest tests/test_db.py -v
```

- [ ] **Step 3: Implement `db.py` schema**

Tables exactly as spec: `sessions`, `transcript_segments`, `jobs`, `reports`.

```sql
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  jd_text TEXT NOT NULL DEFAULT '',
  source_type TEXT,
  media_path TEXT
);
CREATE TABLE IF NOT EXISTS transcript_segments (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  start_ms INTEGER NOT NULL DEFAULT 0,
  end_ms INTEGER NOT NULL DEFAULT 0,
  speaker TEXT NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  candidate_json TEXT NOT NULL,
  hiring_json TEXT NOT NULL,
  model_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

Helpers: `create_session`, `list_sessions`, `get_session`, `update_jd`, `set_source`, `replace_segments`, `list_segments`, `create_job`, `update_job`, `get_job`, `save_report`, `latest_report`.

Use `uuid4().hex` ids; ISO timestamps UTC.

- [ ] **Step 4: Implement `models.py` report schemas**

```python
from typing import Literal
from pydantic import BaseModel, Field

Speaker = Literal["interviewer", "candidate", "unknown"]
Recommendation = Literal["pass", "borderline", "no"]
JobStatus = Literal["queued", "transcribing", "diarizing", "ready", "analyzing", "done", "error"]


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
```

Also define API body models: `CreateSessionIn`, `JdIn`, `PasteIn`, `SegmentIn`, `TranscriptPatchIn`, etc.

- [ ] **Step 5: Tests pass + commit**

```bash
PYTHONPATH=. pytest tests/test_db.py -v
git add backend/app/db.py backend/app/models.py backend/tests/test_db.py
git commit -m "Add SQLite schema and InterviewLens Pydantic models."
```

---

### Task 3: Transcript paste parser

**Files:**
- Create: `backend/app/transcript_parse.py`
- Create: `backend/tests/test_transcript_parse.py`

**Interfaces:**
- Produces: `parse_paste_transcript(text: str) -> list[dict]` each `{idx, start_ms, end_ms, speaker, text}`

- [ ] **Step 1: Failing tests**

```python
from app.transcript_parse import parse_paste_transcript


def test_labeled_lines():
    raw = "Interviewer: Tell me about Python.\nCandidate: I use FastAPI daily.\n"
    segs = parse_paste_transcript(raw)
    assert segs[0]["speaker"] == "interviewer"
    assert "Python" in segs[0]["text"]
    assert segs[1]["speaker"] == "candidate"


def test_unlabeled_becomes_unknown():
    segs = parse_paste_transcript("Just a blob of words about work.")
    assert len(segs) >= 1
    assert segs[0]["speaker"] == "unknown"


def test_empty_raises():
    import pytest
    from app.transcript_parse import ParseError
    with pytest.raises(ParseError):
        parse_paste_transcript("  ")
```

- [ ] **Step 2: Implement parser** — regex `^(Interviewer|Candidate|Unknown)\s*:\s*(.*)$` case-insensitive; consecutive unlabeled lines merge into `unknown`; assign `idx` 0..n-1; `start_ms`/`end_ms` = idx*1000 / (idx+1)*1000 placeholders for paste.

- [ ] **Step 3: Pass + commit** — `Add labeled transcript paste parser.`

---

### Task 4: Session + JD + source routes (no STT yet)

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/tests/test_sessions_api.py`
- Modify: `backend/tests/conftest.py` — tmp SQLite + TestClient

**Interfaces:**
- Produces routes: `GET /health` (basic `ok` + ollama false stub OK), `GET/POST /sessions`, `GET /sessions/{id}`, `PUT /sessions/{id}/jd`, `POST .../source/paste`, `POST .../source/sample`, `POST .../source/upload`

- [ ] **Step 1: conftest with tmp db**

```python
import pytest
from fastapi.testclient import TestClient
import app.config as config
from app import db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path / "uploads")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 2: Failing API tests**

```python
def test_create_and_paste(client):
    r = client.post("/sessions", json={"title": "S1"})
    assert r.status_code == 200
    sid = r.json()["id"]
    jd = "Backend engineer. " + ("Python APIs SQL. " * 5)
    assert client.put(f"/sessions/{sid}/jd", json={"jd_text": jd}).status_code == 200
    paste = "Interviewer: Hi?\nCandidate: Hello, I build APIs.\n"
    r2 = client.post(f"/sessions/{sid}/source/paste", json={"text": paste})
    assert r2.status_code == 200
    detail = client.get(f"/sessions/{sid}").json()
    assert len(detail["segments"]) >= 2
    assert detail["source_type"] == "paste"


def test_analyze_rejected_without_jd_later_placeholder(client):
    # only ensures session exists for now
    r = client.post("/sessions", json={"title": "S2"})
    assert r.status_code == 200
```

- [ ] **Step 3: Implement `main.py` routes** — lifespan `DATA_DIR.mkdir`, `UPLOAD_DIR.mkdir`, `init_db()`. Paste replaces segments + sets `source_type=paste`, clears `media_path`. Sample: load `SAMPLE_JD_PATH` optionally into empty JD if blank; load `SAMPLE_TRANSCRIPT_PATH` via parser; set `source_type=sample_video`; if `SAMPLE_MEDIA_PATH.exists()`, copy/set `media_path`. Upload: validate filename, save bytes under `UPLOAD_DIR/{session_id}{ext}`, set `source_type=upload`, clear segments until transcribe.

- [ ] **Step 4: Pass + commit** — `Add session, JD, and source ingest API routes.`

---

### Task 5: STT service interface + transcribe job + poll

**Files:**
- Create: `backend/app/stt_service.py`
- Create: `backend/app/jobs.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_transcribe_job.py`

**Interfaces:**
- Produces: `transcribe_media(path: Path, hf_token: str) -> list[dict]` (segments)
- Produces: `map_speakers(raw_labels: list[str]) -> list[Speaker]` — first distinct speaker → `interviewer`, second → `candidate`, else `unknown`
- Produces: `start_transcribe_job(session_id: str) -> job_id` runs work via `fastapi.BackgroundTasks` or threading
- Real Whisper/pyannote behind try/except; tests inject mock via monkeypatch

- [ ] **Step 1: Failing test with mocked STT**

```python
def test_transcribe_job_writes_segments(client, monkeypatch, tmp_path):
    from app import stt_service

    def fake_transcribe(path, hf_token=""):
        return [
            {"idx": 0, "start_ms": 0, "end_ms": 1000, "speaker": "interviewer", "text": "Hello"},
            {"idx": 1, "start_ms": 1000, "end_ms": 2000, "speaker": "candidate", "text": "Hi"},
        ]

    monkeypatch.setattr(stt_service, "transcribe_media", fake_transcribe)
    sid = client.post("/sessions", json={"title": "T"}).json()["id"]
    media = tmp_path / "x.wav"
    media.write_bytes(b"RIFF")  # content irrelevant for mock
    # attach upload via API or db helper
    from app import db
    db.set_source(sid, "upload", str(media))
    r = client.post(f"/sessions/{sid}/transcribe")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    # poll until done (TestClient runs background sync if using BackgroundTasks carefully;
    # prefer calling jobs.run_transcribe_job(job_id) directly in test after create)
    from app.jobs import run_transcribe_job
    run_transcribe_job(job_id)
    job = client.get(f"/sessions/{sid}/jobs/{job_id}").json()
    assert job["status"] == "done"
    segs = client.get(f"/sessions/{sid}").json()["segments"]
    assert segs[0]["speaker"] == "interviewer"
```

Note: Implement `POST /transcribe` to create job `queued`, then either BackgroundTasks **or** expose `run_transcribe_job` and call it from BackgroundTasks. Tests call `run_transcribe_job` directly after create for determinism.

- [ ] **Step 2: Implement `stt_service.transcribe_media`**

Logic (real):
1. Status updates happen in `jobs.run_transcribe_job`: set `transcribing` → whisper segments with timestamps → set `diarizing` → pyannote diarization → align → map speakers → `replace_segments` → `ready`/`done`.
2. If no `HF_TOKEN` or pyannote fails: all speakers `unknown`, still return whisper text segments; job completes `done` (not error) unless whisper itself fails → `error`.
3. Paste sessions: `POST /transcribe` may no-op to `done` if segments already exist and no media; if media exists, run STT and replace.

Keep heavy imports inside functions so pytest collection works without torch if mocked before import — structure `stt_service.py` so tests never import torch when monkeypatched at function level.

- [ ] **Step 3: Routes** `POST /sessions/{id}/transcribe`, `GET /sessions/{id}/jobs/{job_id}`, `PATCH /sessions/{id}/transcript`

PATCH body: `{ "segments": [SegmentIn...] }` replaces all segments.

- [ ] **Step 4: Test PATCH**

```python
def test_patch_transcript(client):
    sid = client.post("/sessions", json={"title": "P"}).json()["id"]
    body = {
        "segments": [
            {"idx": 0, "start_ms": 0, "end_ms": 1, "speaker": "candidate", "text": "Edited"}
        ]
    }
    assert client.patch(f"/sessions/{sid}/transcript", json=body).status_code == 200
    assert client.get(f"/sessions/{sid}").json()["segments"][0]["text"] == "Edited"
```

- [ ] **Step 5: Pass + commit** — `Add transcribe jobs, STT interface, and transcript patch.`

---

### Task 6: Ollama client + analyze service (TDD core)

**Files:**
- Create: `backend/app/ollama_client.py`
- Create: `backend/app/analyze_service.py`
- Create: `backend/tests/test_analyze_service.py`

**Interfaces:**
- Produces: `ollama_ok() -> bool`
- Produces: `chat_json(prompt: str) -> dict` (raises on failure)
- Produces: `analyze_interview(jd: str, segments: list[dict]) -> tuple[CandidateReport, HiringReport]`
- Forces `HiringReport.disclaimer = config.HIRING_DISCLAIMER`
- On invalid JSON: retry once; then raise `AnalyzeError`
- Prompt must instruct: quotes only from transcript; missing skills → gaps/unknowns; never invent PASS

- [ ] **Step 1: Happy-path failing test with mock LLM**

```python
from app.analyze_service import analyze_interview
from app.models import CandidateReport, HiringReport


def _valid_payload():
    score = {"score": 70, "rationale": "ok"}
    scores = {
        "jd_match": score,
        "answer_depth": score,
        "communication": score,
        "structure": score,
        "overall": score,
    }
    return {
        "candidate": {
            "scores": scores,
            "summary": "Solid basics.",
            "strengths": [{"point": "Python", "evidence_quote": "I use FastAPI daily"}],
            "improvements": [{"point": "Design", "evidence_quote": "I have not led design", "tip": "Practice system design"}],
            "question_notes": [],
            "readiness_note": "Practice design interviews.",
            "unknowns": [],
        },
        "hiring": {
            "scores": scores,
            "recommendation": "borderline",
            "hire_confidence": 55,
            "fit_summary": "Good Python, weak design.",
            "skill_evidence": [{"skill": "Python", "evidence_quote": "I use FastAPI daily"}],
            "gaps": [{"skill_or_requirement": "System design", "note": "No evidence"}],
            "red_flags": [],
            "follow_up_questions": ["Walk through a service you designed."],
            "unknowns": ["Leadership"],
            "disclaimer": "ignored-by-service",
        },
    }


def test_analyze_happy(monkeypatch):
    from app import analyze_service
    monkeypatch.setattr(analyze_service, "chat_json", lambda prompt: _valid_payload())
    segs = [
        {"speaker": "interviewer", "text": "Tell me about Python."},
        {"speaker": "candidate", "text": "I use FastAPI daily"},
        {"speaker": "interviewer", "text": "System design?"},
        {"speaker": "candidate", "text": "I have not led design"},
    ]
    cand, hire = analyze_interview("Backend engineer needing Python and system design." + (" x" * 20), segs)
    assert isinstance(cand, CandidateReport)
    assert isinstance(hire, HiringReport)
    assert hire.recommendation == "borderline"
    assert "assistive" in hire.disclaimer.lower()
```

- [ ] **Step 2: Failure test — empty inputs**

```python
import pytest
from app.analyze_service import analyze_interview, AnalyzeError


def test_rejects_empty_transcript():
    with pytest.raises(AnalyzeError, match="transcript"):
        analyze_interview("Backend engineer role requiring Python experience here.", [])


def test_rejects_short_jd():
    with pytest.raises(AnalyzeError, match="Job description"):
        analyze_interview("too short", [{"speaker": "candidate", "text": "hi"}])
```

- [ ] **Step 3: Honesty test — mock returns fabricated skill; service strips quotes not in transcript**

```python
def test_strips_invented_evidence(monkeypatch):
    from app import analyze_service
    payload = _valid_payload()
    payload["hiring"]["skill_evidence"] = [
        {"skill": "Kubernetes", "evidence_quote": "I run k8s clusters"}  # not in transcript
    ]
    payload["hiring"]["recommendation"] = "pass"
    monkeypatch.setattr(analyze_service, "chat_json", lambda prompt: payload)
    segs = [{"speaker": "candidate", "text": "I use FastAPI daily"}]
    cand, hire = analyze_interview("Need Kubernetes and Python." + (" y" * 20), segs)
    assert hire.skill_evidence == [] or all(
        "k8s" not in e.evidence_quote.lower() for e in hire.skill_evidence
    )
    # invented quote removed; skill should move toward gaps if still required — minimal rule:
    assert all(e.evidence_quote.lower() in "i use fastapi daily" for e in hire.skill_evidence)
```

Implement `evidence_allowed(quote, transcript_blob) -> bool` as case-insensitive substring check on full transcript text.

- [ ] **Step 4: Implement `ollama_client.py`** — `httpx` POST `{OLLAMA_BASE_URL}/api/chat` with `format: json` if supported, else parse fenced JSON; `ollama_ok` hits `/api/tags`.

- [ ] **Step 5: Implement `analyze_service.py`** — build transcript string with speaker prefixes; single prompt requesting both reports as one JSON object `{candidate, hiring}`; validate with Pydantic; filter evidence; set disclaimer; retry once on `ValidationError`.

- [ ] **Step 6: Pass + commit** — `Add Ollama client and dual-report analyze service.`

---

### Task 7: Analyze job route + reports GET + full health

**Files:**
- Modify: `backend/app/jobs.py`, `backend/app/main.py`
- Create: `backend/tests/test_analyze_api.py`

- [ ] **Step 1: API tests**

```python
def test_analyze_requires_jd_and_segments(client):
    sid = client.post("/sessions", json={"title": "A"}).json()["id"]
    r = client.post(f"/sessions/{sid}/analyze")
    assert r.status_code == 400


def test_analyze_happy(client, monkeypatch):
    from app import analyze_service
    from app.models import CandidateReport, HiringReport
    # reuse builder from unit test module or inline minimal valid models via monkeypatch returning reports
    def fake_analyze(jd, segments):
        from tests.test_analyze_service import _valid_payload
        from app.models import CandidateReport, HiringReport
        from app import config
        p = _valid_payload()
        p["hiring"]["disclaimer"] = config.HIRING_DISCLAIMER
        return CandidateReport.model_validate(p["candidate"]), HiringReport.model_validate(p["hiring"])

    monkeypatch.setattr(analyze_service, "analyze_interview", fake_analyze)
    sid = client.post("/sessions", json={"title": "A"}).json()["id"]
    jd = "Backend engineer. " + ("Python APIs SQL. " * 5)
    client.put(f"/sessions/{sid}/jd", json={"jd_text": jd})
    client.post(
        f"/sessions/{sid}/source/paste",
        json={"text": "Interviewer: Hi?\nCandidate: I use FastAPI daily.\n"},
    )
    r = client.post(f"/sessions/{sid}/analyze")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    from app.jobs import run_analyze_job
    run_analyze_job(job_id)
    reports = client.get(f"/sessions/{sid}/reports").json()
    assert reports["hiring"]["recommendation"] in {"pass", "borderline", "no"}
    assert "assistive" in reports["hiring"]["disclaimer"].lower()
```

- [ ] **Step 2: Implement** `POST /analyze` (400 if empty jd/segments), `run_analyze_job` sets `analyzing` → save report → `done`/`error`, `GET /reports`, enhance `GET /health`:

```json
{
  "ok": true,
  "ollama": true,
  "whisper_ready": true,
  "hf_token_set": false
}
```

`whisper_ready`: try import faster_whisper or flag from config; do not load model in health.

- [ ] **Step 3: Full pytest + commit** — `Add analyze jobs, reports endpoint, and health checks.`

```bash
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest -v
```

---

### Task 8: Frontend scaffold, tokens, API client, job copy helper

**Files:**
- Create: `frontend/` Vite React-TS app
- Create: `frontend/src/styles.css`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/jobCopy.ts`
- Create: `frontend/src/lib/jobCopy.test.ts`
- Create: `frontend/.env.example` (`VITE_API_BASE=http://localhost:8004`)
- Modify: `frontend/index.html` — Google fonts Sora + Manrope

- [ ] **Step 1: Scaffold**

```bash
cd interview-lens
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install && npm install -D vitest jsdom @testing-library/react
# add Tailwind v4 per Vite docs (same approach as voice-faq / whatsapp apps in this portfolio)
```

- [ ] **Step 2: Vitest for job copy**

```typescript
// frontend/src/lib/jobCopy.ts
export function jobStatusMessage(status: string): string {
  switch (status) {
    case "queued":
      return "Waiting to start…";
    case "transcribing":
      return "Transcribing audio…";
    case "diarizing":
      return "Separating speakers…";
    case "analyzing":
      return "Writing both reports…";
    case "ready":
      return "Transcript ready — review speakers, then analyze.";
    case "done":
      return "Done.";
    case "error":
      return "Something went wrong.";
    default:
      return "Working…";
  }
}
```

```typescript
// frontend/src/lib/jobCopy.test.ts
import { describe, it, expect } from "vitest";
import { jobStatusMessage } from "./jobCopy";

describe("jobStatusMessage", () => {
  it("explains diarizing", () => {
    expect(jobStatusMessage("diarizing")).toMatch(/speakers/i);
  });
});
```

- [ ] **Step 3: `api.ts`** — functions mirroring every backend route; `API_BASE` from `import.meta.env.VITE_API_BASE`.

- [ ] **Step 4: `styles.css`** — CSS variables `--ink #0B1220`, `--mint #3EE0B7`, `--amber #F5B942`, atmospheric background, stepper, motions: `.step-in`, `.progress-pulse`, `.report-reveal`. No purple glow / cream terracotta / ReplyDesk green / EchoFAQ orb.

- [ ] **Step 5: Commit** — `Scaffold InterviewLens frontend with API client and tokens.`

---

### Task 9: Home + Setup screens + stepper shell

**Files:**
- Create: `frontend/src/components/Stepper.tsx`
- Create: `frontend/src/components/Home.tsx`
- Create: `frontend/src/components/Setup.tsx`
- Modify: `frontend/src/App.tsx`

**Behavior:**
- Home: **InterviewLens** hero wordmark, short line (“Dual feedback from one interview”), New session, recent list
- Setup: JD textarea + optional file load; source cards Sample | Upload | Paste; primary CTA “Continue to transcript” (disabled until JD valid length + source attached)
- Stepper always visible when inside a session

- [ ] **Step 1: Implement components + wire App state** (`sessionId`, `step: 'home'|'setup'|'transcript'|'reports'`)

- [ ] **Step 2: Manual smoke against API** (backend running)

- [ ] **Step 3: Commit** — `Add InterviewLens home, setup, and stepper shell.`

---

### Task 10: Transcript studio + polling

**Files:**
- Create: `frontend/src/components/TranscriptStudio.tsx`
- Modify: `frontend/src/App.tsx`

**Behavior:**
- List segments; speaker chip cycles interviewer → candidate → unknown; editable text; Save transcript (`PATCH`)
- If `media_path` / upload/sample with media: Transcribe button → poll job every 1s → show `jobStatusMessage`
- Analyze button enabled when JD + ≥1 segment; starts analyze job → on `done` go to Reports
- Empty state CTA if no segments: “Paste a transcript or run transcription”

- [ ] **Step 1: Implement + wire**

- [ ] **Step 2: Smoke** paste path end-to-end without Whisper

- [ ] **Step 3: Commit** — `Add transcript studio with job progress polling.`

---

### Task 11: Dual reports UI

**Files:**
- Create: `frontend/src/components/Reports.tsx`
- Create: `frontend/src/components/ScoreRow.tsx`
- Create: `frontend/src/components/EvidenceCard.tsx`
- Modify: `frontend/src/App.tsx`, `styles.css`

**Behavior:**
- Tabs: Candidate feedback | Hiring decision
- Hiring: large badge PASS / Borderline / NO (mint/amber/ink), confidence, fit summary, lists, disclaimer
- Candidate: summary, strengths, improvements+tips, readiness, unknowns
- Scores first; evidence quotes in mist panels; `.report-reveal` on load
- Back to transcript to re-edit / re-analyze

- [ ] **Step 1: Implement Reports views**

- [ ] **Step 2: Visual check** — scannable, plain labels, brand visible

- [ ] **Step 3: Commit** — `Add dual candidate and hiring report views.`

---

### Task 12: Sample media, Docker, README

**Files:**
- Create: `backend/data/sample_interview.wav` (short; generate with `ffmpeg` or ship tiny PCM wav script in README)
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `docker-compose.yml`
- Create: `.gitignore` (root)
- Create: `.env.example` (root)
- Create: `README.md`

- [ ] **Step 1: Sample wav** — ≤30s spoken or silence+tone acceptable for wiring; preferred: short spoken sample matching sample transcript theme. If binary awkward, document `ffmpeg` one-liner and keep sample path working via transcript-only sample when wav missing.

- [ ] **Step 2: Docker Compose**

- Backend: Python 3.12, port 8000 in container → host **8004**; `OLLAMA_BASE_URL=http://host.docker.internal:11434`; volume `./backend/data:/app/data`
- Frontend: build with `VITE_API_BASE=http://localhost:8004`; nginx on **3004**
- Note: Whisper/pyannote images are heavy — README should prefer **local venv** for STT; Docker API may mark `whisper_ready` false unless image includes deps. YAGNI: document local-run as primary for full STT; Docker still serves paste+analyze if torch omitted via optional requirements split:

  - `requirements.txt` — API core  
  - `requirements-stt.txt` — faster-whisper, torch, pyannote  

  Tests and paste demo use core only.

- [ ] **Step 3: README sections** — what it is; Ollama pull; HF token for pyannote; local run ports 3004/8004; Docker; pytest; limitations; links to spec/plan

- [ ] **Step 4: Verify**

```bash
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest -v
cd frontend && npx vitest run
```

- [ ] **Step 5: Commit** — `Add Docker, README, and sample assets for InterviewLens.`

---

### Task 13: UI polish + final verification

**Files:**
- Modify: `frontend/src/styles.css`, components as needed
- Modify: `README.md` if setup friction found

- [ ] **Step 1: Checklist**

- [ ] InterviewLens wordmark is hero-level on Home  
- [ ] Stepper always clear (Setup → Transcript → Reports)  
- [ ] Progress copy explains transcribing / speakers / reports  
- [ ] Three motions present (step-in, progress-pulse, report-reveal)  
- [ ] Anti-copy: no EchoFAQ / ReplyDesk / FAQ teal / purple / cream-terracotta  
- [ ] Paste path: JD → paste → analyze → both tabs work with mocked or live Ollama  
- [ ] Empty JD / empty transcript fail openly  
- [ ] pytest green with mocks  

- [ ] **Step 2: Final commit if needed** — `Polish InterviewLens UX and verify demo flows.`

---

## Self-review (plan vs spec)

| Spec requirement | Task |
| --- | --- |
| Dual reports candidate + hiring | 6, 7, 11 |
| Hybrid sample / upload / paste | 4, 5, 9, 12 |
| Two-step studio | 9–11 |
| faster-whisper + pyannote, HF token, unknown fallback | 5, 12 |
| Ollama qwen2.5:7b | 6, Global |
| SQLite sessions/segments/jobs/reports | 2, 4–7 |
| Editable speakers before analyze | 5, 10 |
| Evidence filtering / no invent | 6 |
| Job poll statuses | 5, 7, 8, 10 |
| Ports 3004/8004 | Global, 8, 12 |
| Unique UI Sora/Manrope mint/amber | 8, 9, 11, 13 |
| Health + errors 400/503 | 7 |
| pytest happy/fail/honesty | 6, 7 |
| Docker + README | 12 |
| Assistive disclaimer | 6, 11 |
| Out of scope Zoom/cloud/ATS | Global |

**Placeholder scan:** No TBD steps; STT real implementation described; optional `requirements-stt.txt` split documented for Docker weight.

**Type consistency:** Speakers and job statuses match spec literals; `CandidateReport` / `HiringReport` fields align across Tasks 2, 6, 7, 11; API paths match spec table.

**Scope note:** Single coherent app — one plan. Paste+analyze is the reliable demo spine; full Whisper/pyannote is required for video path but mocked in tests.
