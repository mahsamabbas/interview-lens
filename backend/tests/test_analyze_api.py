from app import analyze_service, config, db, jobs
from app.jobs import run_analyze_job
from app.models import CandidateReport, HiringReport
from tests.test_analyze_service import _valid_payload

JD = "Backend engineer. " + ("Python APIs SQL. " * 5)


def _fake_analyze(jd, segments):
    p = _valid_payload()
    p["hiring"]["disclaimer"] = config.HIRING_DISCLAIMER
    return (
        CandidateReport.model_validate(p["candidate"]),
        HiringReport.model_validate(p["hiring"]),
    )


def _ready_session(client) -> str:
    sid = client.post("/sessions", json={"title": "A"}).json()["id"]
    client.put(f"/sessions/{sid}/jd", json={"jd_text": JD})
    client.post(
        f"/sessions/{sid}/source/paste",
        json={"text": "Interviewer: Hi?\nCandidate: I use FastAPI daily.\n"},
    )
    return sid


def test_analyze_requires_jd_and_segments(client):
    sid = client.post("/sessions", json={"title": "A"}).json()["id"]
    assert client.post(f"/sessions/{sid}/analyze").status_code == 400
    client.put(f"/sessions/{sid}/jd", json={"jd_text": JD})
    assert client.post(f"/sessions/{sid}/analyze").status_code == 400


def test_analyze_unknown_session(client):
    assert client.post("/sessions/nope/analyze").status_code == 404
    assert client.get("/sessions/nope/reports").status_code == 404


def test_reports_404_before_analysis(client):
    sid = client.post("/sessions", json={"title": "A"}).json()["id"]
    assert client.get(f"/sessions/{sid}/reports").status_code == 404


def test_analyze_happy(client, monkeypatch):
    monkeypatch.setattr(analyze_service, "analyze_interview", _fake_analyze)
    monkeypatch.setattr(jobs, "run_analyze_job", lambda job_id: None)
    sid = _ready_session(client)
    r = client.post(f"/sessions/{sid}/analyze")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    run_analyze_job(job_id)
    job = client.get(f"/sessions/{sid}/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert job["kind"] == "analyze"
    reports = client.get(f"/sessions/{sid}/reports").json()
    assert reports["hiring"]["recommendation"] in {"pass", "borderline", "no"}
    assert "assistive" in reports["hiring"]["disclaimer"].lower()


def test_run_analyze_job_error(client, monkeypatch):
    def boom(jd, segments):
        raise analyze_service.AnalyzeError("LLM down")

    monkeypatch.setattr(analyze_service, "analyze_interview", boom)
    sid = _ready_session(client)
    job_id = jobs.start_analyze_job(sid)
    run_analyze_job(job_id)
    job = db.get_job(job_id)
    assert job["status"] == "error"
    assert "LLM down" in job["error_message"]
    assert client.get(f"/sessions/{sid}/reports").status_code == 404


def test_health_full(client, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main, "ollama_ok", lambda: True)
    monkeypatch.setattr(config, "HF_TOKEN", "")
    body = client.get("/health").json()
    assert body["ok"] is True
    assert body["ollama"] is True
    assert body["hf_token_set"] is False
    assert isinstance(body["whisper_ready"], bool)
    monkeypatch.setattr(config, "HF_TOKEN", "x")
    assert client.get("/health").json()["hf_token_set"] is True
