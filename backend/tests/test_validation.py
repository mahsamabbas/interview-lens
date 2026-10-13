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


def test_media_accepts_mov():
    assert validate_media_filename("interview.MOV") == ".mov"
