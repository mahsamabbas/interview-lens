import re

_LABEL_RE = re.compile(
    r"^(Interviewer|Candidate|Unknown)\s*:\s*(.*)$",
    re.IGNORECASE,
)
# e.g. "00:00 to 03:00 | Introduction and Background"
_SECTION_RE = re.compile(
    r"^\d{1,2}:\d{2}\s+to\s+\d{1,2}:\d{2}\s*\|",
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

    def append_to_current(line: str) -> None:
        """Attach unlabeled continuation to the open labeled turn."""
        if not segments:
            unknown_lines.append(line)
            return
        prev = segments[-1]
        prev["text"] = f"{prev['text']}\n{line}".strip()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            # Blank line ends a leading unlabeled blob; labeled turns stay open
            # so the next paragraph can continue the same speaker.
            if unknown_lines and not segments:
                flush_unknown()
            continue
        if _SECTION_RE.match(stripped):
            flush_unknown()
            continue
        m = _LABEL_RE.match(stripped)
        if m:
            flush_unknown()
            speaker = m.group(1).lower()
            body = m.group(2).strip()
            segments.append(_segment(speaker, body, len(segments)))
        elif segments:
            append_to_current(stripped)
        else:
            unknown_lines.append(stripped)

    flush_unknown()

    if not segments:
        raise ParseError("empty transcript")

    return segments
