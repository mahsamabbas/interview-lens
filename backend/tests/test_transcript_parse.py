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


def test_empty_raises():
    import pytest
    from app.transcript_parse import ParseError
    with pytest.raises(ParseError):
        parse_paste_transcript("  ")
