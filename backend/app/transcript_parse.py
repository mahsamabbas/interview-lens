import re

_LABEL_RE = re.compile(
    r"^(Interviewer|Candidate|Unknown)\s*:\s*(.*)$",
    re.IGNORECASE,
)


class ParseError(ValueError):
    pass


def _segment(speaker: str, text: str, idx: int) -> dict:
    return {
        "idx": idx,
        "start_ms": idx * 1000,
        "end_ms": (idx + 1) * 1000,
        "speaker": speaker,
        "text": text,
    }


def parse_paste_transcript(text: str) -> list[dict]:
    if not text or not text.strip():
        raise ParseError("empty transcript")

    segments: list[dict] = []
    unknown_lines: list[str] = []

    def flush_unknown() -> None:
        nonlocal unknown_lines
        if not unknown_lines:
            return
        body = "\n".join(unknown_lines).strip()
        if body:
            segments.append(_segment("unknown", body, len(segments)))
        unknown_lines = []

    for line in text.splitlines():
        m = _LABEL_RE.match(line.strip())
        if m:
            flush_unknown()
            speaker = m.group(1).lower()
            body = m.group(2).strip()
            segments.append(_segment(speaker, body, len(segments)))
        elif line.strip():
            unknown_lines.append(line.strip())
        elif unknown_lines:
            flush_unknown()

    flush_unknown()

    if not segments:
        raise ParseError("empty transcript")

    return segments
