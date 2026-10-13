"""Speech-to-text + diarization.

Heavy deps (faster-whisper, torch, pyannote) are imported lazily inside
functions so importing this module (and running pytest with STT mocked)
never requires them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from app import config
from app.models import Speaker

logger = logging.getLogger(__name__)

_whisper_model = None
_diarize_pipeline = None
_diarize_pipeline_token: str | None = None


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


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:  # pragma: no cover - depends on env
            raise RuntimeError(
                "faster-whisper is not installed; install it to transcribe media"
            ) from e
        _whisper_model = WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    return _whisper_model


def _run_whisper(path: Path) -> list[dict]:
    model = _get_whisper()
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


def _extract_diarization_turns(diarization) -> list[tuple[float, float, str]]:
    """Normalize pyannote 3.x Annotation and 4.x DiarizeOutput to turns."""
    # community-1 / pyannote.audio 4.x
    exclusive = getattr(diarization, "exclusive_speaker_diarization", None)
    speaker_diarization = exclusive or getattr(diarization, "speaker_diarization", None)
    if speaker_diarization is not None:
        turns: list[tuple[float, float, str]] = []
        for turn, speaker in speaker_diarization:
            label = str(speaker)
            turns.append((float(turn.start), float(turn.end), label))
        if turns:
            return turns

    # legacy Annotation API (speaker-diarization-3.1)
    if hasattr(diarization, "itertracks"):
        return [
            (float(turn.start), float(turn.end), str(label))
            for turn, _, label in diarization.itertracks(yield_label=True)
        ]

    raise RuntimeError(f"Unsupported diarization output type: {type(diarization)!r}")


def _get_diarize_pipeline(hf_token: str):
    global _diarize_pipeline, _diarize_pipeline_token
    if _diarize_pipeline is None or _diarize_pipeline_token != hf_token:
        from pyannote.audio import Pipeline

        model_id = config.DIARIZATION_MODEL
        try:
            pipeline = Pipeline.from_pretrained(model_id, token=hf_token)
        except TypeError:  # older pyannote
            pipeline = Pipeline.from_pretrained(model_id, use_auth_token=hf_token)
        if pipeline is None:
            raise RuntimeError("pyannote pipeline unavailable (check HF_TOKEN/model access)")
        _diarize_pipeline = pipeline
        _diarize_pipeline_token = hf_token
    return _diarize_pipeline


def _run_diarize(path: Path, hf_token: str) -> list[tuple[float, float, str]]:
    """Return (start_s, end_s, label) turns. Raises on any failure."""
    pipeline = _get_diarize_pipeline(hf_token)
    # Interviews are almost always two speakers — helps clustering.
    try:
        diarization = pipeline(str(path), num_speakers=2)
    except TypeError:
        diarization = pipeline(str(path))
    turns = _extract_diarization_turns(diarization)
    if not turns:
        raise RuntimeError("diarization returned no speaker turns")
    return turns


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


def transcribe_media(
    path: Path,
    hf_token: str = "",
    on_phase: Callable[[str], None] | None = None,
) -> list[dict]:
    """Transcribe media into segments: idx/start_ms/end_ms/speaker/text.

    Whisper failure raises. Diarization is best-effort: without an HF token or
    if pyannote fails, every segment gets speaker "unknown".
    `on_phase` (optional) is called with "transcribing" then "diarizing" (only
    when diarization will actually run).
    """
    path = Path(path)
    if on_phase:
        on_phase("transcribing")
    segments = _run_whisper(path)
    labels: list[str | None] = [None] * len(segments)
    if hf_token and segments:
        if on_phase:
            on_phase("diarizing")
        try:
            labels = _align(segments, _run_diarize(path, hf_token))
        except Exception as exc:
            # Best-effort: keep transcript text; UI can relabel speakers.
            logger.warning(
                "Diarization failed (%s); labeling speakers as unknown",
                exc,
                exc_info=True,
            )
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
