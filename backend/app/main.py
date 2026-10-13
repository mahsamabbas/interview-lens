import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app import config, db
from app.models import (
    CreateSessionIn,
    CreateSessionOut,
    JdIn,
    PasteIn,
    SessionOut,
    SessionSummaryOut,
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


@app.get("/health")
def health():
    # Ollama probe is a stub until the analyze task lands.
    return {"status": "ok", "ollama": False}


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
