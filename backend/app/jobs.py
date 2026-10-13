import inspect
from pathlib import Path

from app import config, db, stt_service
from app.models import SegmentIn


def start_transcribe_job(session_id: str) -> str:
    """Create a queued transcribe job. Caller schedules run_transcribe_job."""
    return db.create_job(session_id, "transcribe", "queued")


def complete_job_without_stt(session_id: str) -> str:
    """Job for sessions whose transcript already exists and have no media."""
    return db.create_job(session_id, "transcribe", "done")


def _accepts_on_phase(fn) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return "on_phase" in params or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    )


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
        fn = stt_service.transcribe_media
        kwargs = {}
        if _accepts_on_phase(fn):
            kwargs["on_phase"] = lambda status: db.update_job(job_id, status)
        raw = fn(Path(media_path), config.HF_TOKEN, **kwargs)
        segments = [
            SegmentIn(**{**seg, "idx": i}).model_dump() for i, seg in enumerate(raw)
        ]
        if not segments:
            raise RuntimeError("No speech detected in media")
        db.replace_segments(job["session_id"], segments)
        db.update_job(job_id, "done")
    except Exception as e:
        db.update_job(job_id, "error", str(e) or e.__class__.__name__)
