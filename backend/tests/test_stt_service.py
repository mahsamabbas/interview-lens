"""Exercise real transcribe_media orchestration with whisper/pyannote stubbed."""

from pathlib import Path

from app import stt_service

WHISPER = [
    {"start_ms": 0, "end_ms": 1000, "text": "Hello"},
    {"start_ms": 1000, "end_ms": 2000, "text": "Hi"},
]


def _patch_whisper(monkeypatch):
    monkeypatch.setattr(stt_service, "_run_whisper", lambda path: [dict(s) for s in WHISPER])


def _no_diarize(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("diarize must not run")

    monkeypatch.setattr(stt_service, "_run_diarize", boom)


def test_no_hf_token_all_unknown(monkeypatch):
    _patch_whisper(monkeypatch)
    _no_diarize(monkeypatch)
    phases = []
    out = stt_service.transcribe_media(Path("x.wav"), hf_token="", on_phase=phases.append)
    assert [s["speaker"] for s in out] == ["unknown", "unknown"]
    assert [s["idx"] for s in out] == [0, 1]
    assert [s["text"] for s in out] == ["Hello", "Hi"]
    assert phases == ["transcribing"]


def test_with_token_diarizes_and_reports_phase(monkeypatch):
    _patch_whisper(monkeypatch)
    monkeypatch.setattr(
        stt_service,
        "_run_diarize",
        lambda path, tok: [(0.0, 1.0, "S0"), (1.0, 2.0, "S1")],
    )
    phases = []
    out = stt_service.transcribe_media(Path("x.wav"), hf_token="tok", on_phase=phases.append)
    assert [s["speaker"] for s in out] == ["interviewer", "candidate"]
    assert phases == ["transcribing", "diarizing"]


def test_diarize_failure_falls_back_to_unknown(monkeypatch):
    _patch_whisper(monkeypatch)

    def fail(path, tok):
        raise RuntimeError("pyannote down")

    monkeypatch.setattr(stt_service, "_run_diarize", fail)
    out = stt_service.transcribe_media(Path("x.wav"), hf_token="tok")
    assert [s["speaker"] for s in out] == ["unknown", "unknown"]


def test_whisper_failure_raises(monkeypatch):
    def fail(path):
        raise RuntimeError("no whisper")

    monkeypatch.setattr(stt_service, "_run_whisper", fail)
    import pytest

    with pytest.raises(RuntimeError, match="no whisper"):
        stt_service.transcribe_media(Path("x.wav"))


class _Turn:
    def __init__(self, start, end):
        self.start = start
        self.end = end


class _CommunityOut:
    def __init__(self):
        self.speaker_diarization = [
            (_Turn(0.0, 1.0), "SPEAKER_00"),
            (_Turn(1.0, 2.0), "SPEAKER_01"),
        ]


def test_extract_community_diarization_turns():
    turns = stt_service._extract_diarization_turns(_CommunityOut())
    assert turns == [(0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01")]
