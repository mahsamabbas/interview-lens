from pathlib import Path

from app.transcript_parse import parse_paste_transcript


def test_labeled_lines():
    raw = "Interviewer: Tell me about Python.\nCandidate: I use FastAPI daily.\n"
    segs = parse_paste_transcript(raw)
    assert segs[0]["speaker"] == "interviewer"
    assert "Python" in segs[0]["text"]
    assert segs[1]["speaker"] == "candidate"


def test_unlabeled_becomes_unknown():
    segs = parse_paste_transcript("Just a blob of words about work.")
    assert len(segs) >= 1
    assert segs[0]["speaker"] == "unknown"


def test_continuation_lines_keep_previous_speaker():
    raw = (
        "Candidate: First sentence.\n"
        "Second sentence continues.\n"
        "Third sentence too.\n"
        "Interviewer: Follow-up?\n"
    )
    segs = parse_paste_transcript(raw)
    assert [s["speaker"] for s in segs] == ["candidate", "interviewer"]
    assert "Second sentence" in segs[0]["text"]
    assert "Third sentence" in segs[0]["text"]
    assert segs[1]["text"] == "Follow-up?"


def test_section_headers_are_skipped():
    raw = (
        "00:00 to 03:00 | Introduction and Background\n"
        "Interviewer: Hello.\n"
        "Candidate: Hi there.\n"
        "03:00 to 07:00 | AWS Infrastructure\n"
        "Interviewer: Next topic.\n"
    )
    segs = parse_paste_transcript(raw)
    assert [s["speaker"] for s in segs] == ["interviewer", "candidate", "interviewer"]
    assert all("|" not in s["text"] for s in segs)
    assert all("00:00" not in s["text"] for s in segs)


def test_real_interview_transcript_file_has_few_unknowns():
    path = Path(__file__).resolve().parents[3] / "transcript.txt"
    if not path.is_file():
        path = Path("/Users/azc/Desktop/azc/mahsamabbas_repos/transcript.txt")
    raw = path.read_text(encoding="utf-8")
    segs = parse_paste_transcript(raw)
    speakers = [s["speaker"] for s in segs]
    unknown = sum(1 for s in speakers if s == "unknown")
    assert len(segs) > 40
    assert "interviewer" in speakers and "candidate" in speakers
    assert unknown == 0


def test_empty_raises():
    import pytest
    from app.transcript_parse import ParseError
    with pytest.raises(ParseError):
        parse_paste_transcript("  ")
