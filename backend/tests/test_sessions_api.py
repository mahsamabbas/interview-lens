JD = "Backend engineer. " + ("Python APIs SQL. " * 5)


def test_create_and_paste(client):
    r = client.post("/sessions", json={"title": "S1"})
    assert r.status_code == 200
    sid = r.json()["id"]
    jd = "Backend engineer. " + ("Python APIs SQL. " * 5)
    assert client.put(f"/sessions/{sid}/jd", json={"jd_text": jd}).status_code == 200
    paste = "Interviewer: Hi?\nCandidate: Hello, I build APIs.\n"
    r2 = client.post(f"/sessions/{sid}/source/paste", json={"text": paste})
    assert r2.status_code == 200
    detail = client.get(f"/sessions/{sid}").json()
    assert len(detail["segments"]) >= 2
    assert detail["source_type"] == "paste"


def test_analyze_rejected_without_jd_later_placeholder(client):
    # only ensures session exists for now
    r = client.post("/sessions", json={"title": "S2"})
    assert r.status_code == 200


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_sessions(client):
    client.post("/sessions", json={"title": "A"})
    client.post("/sessions", json={"title": "B"})
    r = client.get("/sessions")
    assert r.status_code == 200
    assert {s["title"] for s in r.json()} == {"A", "B"}


def test_get_missing_session_404(client):
    assert client.get("/sessions/nope").status_code == 404
    assert client.put("/sessions/nope/jd", json={"jd_text": JD}).status_code == 404


def test_jd_too_short_rejected(client):
    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    r = client.put(f"/sessions/{sid}/jd", json={"jd_text": "short"})
    assert r.status_code == 400


def test_paste_empty_rejected(client):
    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    r = client.post(f"/sessions/{sid}/source/paste", json={"text": "   "})
    assert r.status_code == 400


def test_paste_clears_media_path_and_replaces_segments(client):
    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    client.post(f"/sessions/{sid}/source/sample")
    client.post(f"/sessions/{sid}/source/paste", json={"text": "Candidate: only me"})
    d = client.get(f"/sessions/{sid}").json()
    assert d["media_path"] is None
    assert len(d["segments"]) == 1
    assert d["source_type"] == "paste"


def test_sample_loads_transcript_and_jd(client):
    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    r = client.post(f"/sessions/{sid}/source/sample")
    assert r.status_code == 200
    d = client.get(f"/sessions/{sid}").json()
    assert d["source_type"] == "sample_video"
    assert len(d["segments"]) >= 2
    assert d["jd_text"].strip()


def test_sample_keeps_existing_jd(client):
    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    client.put(f"/sessions/{sid}/jd", json={"jd_text": JD})
    client.post(f"/sessions/{sid}/source/sample")
    assert client.get(f"/sessions/{sid}").json()["jd_text"] == JD.strip()


def test_upload_saves_file_and_clears_segments(client):
    import app.config as config

    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    client.post(f"/sessions/{sid}/source/paste", json={"text": "Candidate: hi"})
    r = client.post(
        f"/sessions/{sid}/source/upload",
        files={"file": ("talk.wav", b"RIFFfake", "audio/wav")},
    )
    assert r.status_code == 200
    d = client.get(f"/sessions/{sid}").json()
    assert d["source_type"] == "upload"
    assert d["segments"] == []
    assert d["media_path"].endswith(f"{sid}.wav")
    assert (config.UPLOAD_DIR / f"{sid}.wav").read_bytes() == b"RIFFfake"


def test_upload_bad_extension_rejected(client):
    sid = client.post("/sessions", json={"title": "S"}).json()["id"]
    r = client.post(
        f"/sessions/{sid}/source/upload",
        files={"file": ("evil.exe", b"x", "application/octet-stream")},
    )
    assert r.status_code == 400
