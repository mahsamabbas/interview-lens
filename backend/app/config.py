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
# Newer pyannote.audio prefers community-1; 3.1 still works if gated access is set.
DIARIZATION_MODEL = os.getenv(
    "DIARIZATION_MODEL",
    "pyannote/speaker-diarization-community-1",
)
MIN_JD_CHARS = 40
MAX_JD_CHARS = 20_000
ALLOWED_MEDIA = {".wav", ".mp3", ".m4a", ".webm", ".mp4", ".mov"}
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
