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
