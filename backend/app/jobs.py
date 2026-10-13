from pathlib import Path

from app import config, db, stt_service
from app.models import SegmentIn


def start_transcribe_job(session_id: str) -> str:
    """Create a queued transcribe job. Caller schedules run_transcribe_job."""
    return db.create_job(session_id, "transcribe", "queued")


def complete_job_without_stt(session_id: str) -> str:
    """Job for sessions whose transcript already exists and have no media."""
    return db.create_job(session_id, "transcribe", "done")


def run_transcribe_job(job_id: str) -> None:
    job = db.get_job(job_id)
    if job is None:
        return
    try:
        session = db.get_session(job["session_id"])
        media_path = (session or {}).get("media_path")
        if not media_path or not Path(media_path).exists():
            raise RuntimeError("No media file available to transcribe")

        db.update_job(job_id, "transcribing")
        # Looked up via module attribute so tests can monkeypatch it.
        raw = stt_service.transcribe_media(Path(media_path), config.HF_TOKEN)
        segments = [
            SegmentIn(**{**seg, "idx": i}).model_dump() for i, seg in enumerate(raw)
        ]
        if not segments:
            raise RuntimeError("No speech detected in media")
        db.replace_segments(job["session_id"], segments)
        db.update_job(job_id, "done")
    except Exception as e:
        db.update_job(job_id, "error", str(e) or e.__class__.__name__)
