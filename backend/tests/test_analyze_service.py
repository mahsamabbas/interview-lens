import copy

import pytest

from app.analyze_service import AnalyzeError, analyze_interview, evidence_allowed
from app.models import CandidateReport, HiringReport

JD = "Backend engineer needing Python and system design." + (" x" * 20)


def _valid_payload():
    score = {"score": 70, "rationale": "ok"}
    scores = {
        "jd_match": score,
        "answer_depth": score,
        "communication": score,
        "structure": score,
        "overall": score,
    }
    return {
        "candidate": {
            "scores": scores,
            "summary": "Solid basics.",
            "strengths": [{"point": "Python", "evidence_quote": "I use FastAPI daily"}],
            "improvements": [
                {
                    "point": "Design",
                    "evidence_quote": "I have not led design",
                    "tip": "Practice system design",
                }
            ],
            "question_notes": [],
            "readiness_note": "Practice design interviews.",
            "unknowns": [],
        },
        "hiring": {
            "scores": scores,
            "recommendation": "borderline",
            "hire_confidence": 55,
            "fit_summary": "Good Python, weak design.",
            "skill_evidence": [{"skill": "Python", "evidence_quote": "I use FastAPI daily"}],
            "gaps": [{"skill_or_requirement": "System design", "note": "No evidence"}],
            "red_flags": [],
            "follow_up_questions": ["Walk through a service you designed."],
            "unknowns": ["Leadership"],
            "disclaimer": "ignored-by-service",
        },
    }


SEGS = [
    {"speaker": "interviewer", "text": "Tell me about Python."},
    {"speaker": "candidate", "text": "I use FastAPI daily"},
    {"speaker": "interviewer", "text": "System design?"},
    {"speaker": "candidate", "text": "I have not led design"},
]


def test_analyze_happy(monkeypatch):
    from app import analyze_service

    monkeypatch.setattr(
        analyze_service, "chat_json", lambda prompt, **kwargs: _valid_payload()
    )
    cand, hire = analyze_interview(JD, SEGS)
    assert isinstance(cand, CandidateReport)
    assert isinstance(hire, HiringReport)
    assert hire.recommendation == "borderline"
    assert "assistive" in hire.disclaimer.lower()
    assert hire.disclaimer != "ignored-by-service"
    assert len(cand.strengths) == 1
    assert len(hire.skill_evidence) == 1


def test_rejects_empty_transcript():
    with pytest.raises(AnalyzeError, match="transcript"):
        analyze_interview("Backend engineer role requiring Python experience here.", [])


def test_rejects_short_jd():
    with pytest.raises(AnalyzeError, match="Job description"):
        analyze_interview("too short", [{"speaker": "candidate", "text": "hi"}])


def test_strips_invented_evidence(monkeypatch):
    from app import analyze_service

    payload = _valid_payload()
    payload["hiring"]["skill_evidence"] = [
        {"skill": "Kubernetes", "evidence_quote": "I run k8s clusters"}
    ]
    payload["hiring"]["red_flags"] = [{"note": "x", "evidence_quote": "I lied once"}]
    payload["candidate"]["strengths"].append(
        {"point": "K8s", "evidence_quote": "I run k8s clusters"}
    )
    payload["hiring"]["recommendation"] = "pass"
    payload["hiring"]["hire_confidence"] = 85
    monkeypatch.setattr(
        analyze_service, "chat_json", lambda prompt, **kwargs: payload
    )
    segs = [{"speaker": "candidate", "text": "I use FastAPI daily"}]
    cand, hire = analyze_interview("Need Kubernetes and Python." + (" y" * 20), segs)
    assert hire.skill_evidence == []
    assert hire.recommendation == "borderline"
    assert hire.hire_confidence == 60
    assert hire.red_flags == []
    assert [s.point for s in cand.strengths] == ["Python"]
    # stripped skill must surface as a gap, not silently vanish
    assert any(g.skill_or_requirement == "Kubernetes" for g in hire.gaps)


def test_evidence_allowed_case_insensitive():
    assert evidence_allowed("i USE fastapi", "Candidate: I use FastAPI daily")
    assert not evidence_allowed("k8s", "I use FastAPI daily")
    assert not evidence_allowed("", "I use FastAPI daily")


def test_retries_once_on_invalid_then_succeeds(monkeypatch):
    from app import analyze_service

    calls = []

    def fake(prompt, **kwargs):
        calls.append(prompt)
        return {"candidate": {}, "hiring": {}} if len(calls) == 1 else _valid_payload()

    monkeypatch.setattr(analyze_service, "chat_json", fake)
    cand, _ = analyze_interview(JD, SEGS)
    assert len(calls) == 2
    assert isinstance(cand, CandidateReport)


def test_raises_after_second_invalid(monkeypatch):
    from app import analyze_service

    calls = []

    def fake(prompt, **kwargs):
        calls.append(prompt)
        return {"bad": True}

    monkeypatch.setattr(analyze_service, "chat_json", fake)
    with pytest.raises(AnalyzeError):
        analyze_interview(JD, SEGS)
    assert len(calls) == 2


def test_prompt_contains_guardrails(monkeypatch):
    from app import analyze_service

    seen = []

    def fake(prompt, **kwargs):
        seen.append(prompt)
        return copy.deepcopy(_valid_payload())

    monkeypatch.setattr(analyze_service, "chat_json", fake)
    analyze_interview(JD, SEGS)
    p = seen[0].lower()
    assert "hiring" in p and "transcript" in p
    assert "never invent" in p
    assert "candidate: i use fastapi daily" in p
