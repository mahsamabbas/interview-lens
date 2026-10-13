"""Speech-to-text + diarization.

Heavy deps (faster-whisper, torch, pyannote) are imported lazily inside
functions so importing this module (and running pytest with STT mocked)
never requires them.
"""

from pathlib import Path

from app import config
from app.models import Speaker

_DIARIZATION_MODEL = "pyannote/speaker-diarization-3.1"


def map_speakers(raw_labels: list[str | None]) -> list[Speaker]:
    """Map raw diarization labels to roles by first appearance.

    First distinct label -> interviewer, second -> candidate, rest -> unknown.
    A None/empty label maps to unknown and does not consume a role.
    """
    order: dict[str, Speaker] = {}
    out: list[Speaker] = []
    for label in raw_labels:
        if not label:
            out.append("unknown")
            continue
        if label not in order:
            n = len(order)
            order[label] = "interviewer" if n == 0 else "candidate" if n == 1 else "unknown"
        out.append(order[label])
    return out


def _whisper_segments(path: Path) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # pragma: no cover - depends on env
        raise RuntimeError(
            "faster-whisper is not installed; install it to transcribe media"
        ) from e
    model = WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    segments, _info = model.transcribe(str(path))
    out = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            out.append(
                {
                    "start_ms": int(seg.start * 1000),
                    "end_ms": int(seg.end * 1000),
                    "text": text,
                }
            )
    return out


def _diarize(path: Path, hf_token: str) -> list[tuple[float, float, str]]:
    """Return (start_s, end_s, label) turns. Raises on any failure."""
    from pyannote.audio import Pipeline

    try:
        pipeline = Pipeline.from_pretrained(_DIARIZATION_MODEL, token=hf_token)
    except TypeError:  # older pyannote
        pipeline = Pipeline.from_pretrained(_DIARIZATION_MODEL, use_auth_token=hf_token)
    if pipeline is None:
        raise RuntimeError("pyannote pipeline unavailable (check HF_TOKEN/model access)")
    diarization = pipeline(str(path))
    return [
        (turn.start, turn.end, label)
        for turn, _, label in diarization.itertracks(yield_label=True)
    ]


def _align(segments: list[dict], turns: list[tuple[float, float, str]]) -> list[str | None]:
    """Pick the diarization label with the largest overlap per text segment."""
    labels: list[str | None] = []
    for seg in segments:
        s, e = seg["start_ms"] / 1000, seg["end_ms"] / 1000
        best, best_overlap = None, 0.0
        for ts, te, label in turns:
            overlap = min(e, te) - max(s, ts)
            if overlap > best_overlap:
                best, best_overlap = label, overlap
        labels.append(best)
    return labels


def transcribe_media(path: Path, hf_token: str = "") -> list[dict]:
    """Transcribe media into segments: idx/start_ms/end_ms/speaker/text.

    Whisper failure raises. Diarization is best-effort: without an HF token or
    if pyannote fails, every segment gets speaker "unknown".
    """
    path = Path(path)
    segments = _whisper_segments(path)
    labels: list[str | None] = [None] * len(segments)
    if hf_token and segments:
        try:
            labels = _align(segments, _diarize(path, hf_token))
        except Exception:
            labels = [None] * len(segments)
    speakers = map_speakers(labels)
    return [
        {
            "idx": i,
            "start_ms": seg["start_ms"],
            "end_ms": seg["end_ms"],
            "speaker": speakers[i],
            "text": seg["text"],
        }
        for i, seg in enumerate(segments)
    ]
