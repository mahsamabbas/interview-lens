import importlib.util
import shutil
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import config, db, jobs
from app.ollama_client import ollama_ok
from app.models import (
    CreateSessionIn,
    CreateSessionOut,
    JdIn,
    JobCreatedOut,
    JobOut,
    PasteIn,
    ReportsOut,
    SessionOut,
    SessionSummaryOut,
    TranscriptPatchIn,
)
from app.transcript_parse import ParseError, parse_paste_transcript
from app.validation import ValidationError, validate_jd_text, validate_media_filename


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(title="InterviewLens API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_session(session_id: str) -> dict:
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _whisper_ready() -> bool:
    # Import check only; never load the model from the health endpoint.
    try:
        return importlib.util.find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        return False


@app.get("/health")
def health():
    return {
        "ok": True,
        "status": "ok",
        "ollama": ollama_ok(),
        "whisper_ready": _whisper_ready(),
        "hf_token_set": bool(config.HF_TOKEN),
    }


@app.get("/sessions", response_model=list[SessionSummaryOut])
def list_sessions():
    return db.list_sessions()


@app.post("/sessions", response_model=CreateSessionOut)
def create_session(body: CreateSessionIn):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    return {"id": db.create_session(title)}


@app.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str):
    session = _require_session(session_id)
    return {**session, "segments": db.list_segments(session_id)}


@app.put("/sessions/{session_id}/jd")
def put_jd(session_id: str, body: JdIn):
    _require_session(session_id)
    try:
        cleaned = validate_jd_text(body.jd_text)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.update_jd(session_id, cleaned)
    return {"ok": True}


@app.post("/sessions/{session_id}/source/paste")
def source_paste(session_id: str, body: PasteIn):
    _require_session(session_id)
    try:
        segments = parse_paste_transcript(body.text)
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.replace_segments(session_id, segments)
    db.set_source(session_id, "paste", None)
    return {"ok": True, "segments": len(segments)}


@app.post("/sessions/{session_id}/source/sample")
def source_sample(session_id: str):
    session = _require_session(session_id)
    if not config.SAMPLE_TRANSCRIPT_PATH.exists():
        raise HTTPException(status_code=500, detail="Sample transcript missing")
    try:
        segments = parse_paste_transcript(
            config.SAMPLE_TRANSCRIPT_PATH.read_text(encoding="utf-8")
        )
    except ParseError as e:
        raise HTTPException(status_code=500, detail=f"Sample transcript invalid: {e}")

    if not (session["jd_text"] or "").strip() and config.SAMPLE_JD_PATH.exists():
        db.update_jd(session_id, config.SAMPLE_JD_PATH.read_text(encoding="utf-8").strip())

    db.replace_segments(session_id, segments)
    media = str(config.SAMPLE_MEDIA_PATH) if config.SAMPLE_MEDIA_PATH.exists() else None
    db.set_source(session_id, "sample_video", media)
    return {"ok": True, "segments": len(segments)}


@app.post("/sessions/{session_id}/source/upload")
def source_upload(session_id: str, file: UploadFile = File(...)):
    _require_session(session_id)
    try:
        ext = validate_media_filename(file.filename or "")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.UPLOAD_DIR / f"{session_id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    db.replace_segments(session_id, [])
    db.set_source(session_id, "upload", str(dest))
    return {"ok": True, "media_path": str(dest)}


@app.post("/sessions/{session_id}/transcribe", response_model=JobCreatedOut)
def transcribe(session_id: str, background: BackgroundTasks):
    session = _require_session(session_id)
    media = session.get("media_path")
    has_media = bool(media) and Path(media).exists()
    if has_media:
        job_id = jobs.start_transcribe_job(session_id)
        background.add_task(jobs.run_transcribe_job, job_id)
        return {"job_id": job_id}
    if db.list_segments(session_id):
        return {"job_id": jobs.complete_job_without_stt(session_id)}
    raise HTTPException(status_code=400, detail="No media or transcript to transcribe")


@app.get("/sessions/{session_id}/jobs/{job_id}", response_model=JobOut)
def get_job(session_id: str, job_id: str):
    _require_session(session_id)
    job = db.get_job(job_id)
    if job is None or job["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.patch("/sessions/{session_id}/transcript")
def patch_transcript(session_id: str, body: TranscriptPatchIn):
    _require_session(session_id)
    db.replace_segments(session_id, [s.model_dump() for s in body.segments])
    return {"ok": True, "segments": len(body.segments)}


@app.post("/sessions/{session_id}/analyze", response_model=JobCreatedOut)
def analyze(session_id: str, background: BackgroundTasks):
    session = _require_session(session_id)
    if not (session.get("jd_text") or "").strip():
        raise HTTPException(status_code=400, detail="Job description is required")
    if not db.list_segments(session_id):
        raise HTTPException(status_code=400, detail="Transcript is required")
    job_id = jobs.start_analyze_job(session_id)
    background.add_task(jobs.run_analyze_job, job_id)
    return {"job_id": job_id}


@app.get("/sessions/{session_id}/reports", response_model=ReportsOut)
def get_reports(session_id: str):
    _require_session(session_id)
    report = db.latest_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="No report yet")
    return {"candidate": report["candidate_json"], "hiring": report["hiring_json"]}
