from app import db

JD = "Backend engineer. " + ("Python APIs SQL. " * 5)


def _ready_session(client) -> str:
    sid = client.post("/sessions", json={"title": "A"}).json()["id"]
    client.put(f"/sessions/{sid}/jd", json={"jd_text": JD})
    client.post(
        f"/sessions/{sid}/source/paste",
        json={"text": "Interviewer: Hi?\nCandidate: I use FastAPI daily.\n"},
    )
    return sid


def _session_with_media(client, tmp_path):
    sid = client.post("/sessions", json={"title": "T"}).json()["id"]
    media = tmp_path / "x.wav"
    media.write_bytes(b"RIFF")
    db.set_source(sid, "upload", str(media))
    return sid


def test_analyze_rejects_when_job_in_flight(client):
    sid = _ready_session(client)
    db.create_job(sid, "analyze", "queued")
    r = client.post(f"/sessions/{sid}/analyze")
    assert r.status_code == 409
    assert "already running" in r.json()["detail"].lower()


def test_transcribe_rejects_when_job_in_flight(client, tmp_path):
    sid = _session_with_media(client, tmp_path)
    db.create_job(sid, "transcribe", "transcribing")
    r = client.post(f"/sessions/{sid}/transcribe")
    assert r.status_code == 409
