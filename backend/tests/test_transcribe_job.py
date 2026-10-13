import pytest

from app import db, stt_service
from app.jobs import run_transcribe_job

FAKE_SEGMENTS = [
    {"idx": 0, "start_ms": 0, "end_ms": 1000, "speaker": "interviewer", "text": "Hello"},
    {"idx": 1, "start_ms": 1000, "end_ms": 2000, "speaker": "candidate", "text": "Hi"},
]


def _session_with_media(client, tmp_path, name="x.wav"):
    sid = client.post("/sessions", json={"title": "T"}).json()["id"]
    media = tmp_path / name
    media.write_bytes(b"RIFF")  # content irrelevant for mock
    db.set_source(sid, "upload", str(media))
    return sid


def test_transcribe_job_writes_segments(client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        stt_service, "transcribe_media", lambda path, hf_token="": FAKE_SEGMENTS
    )
    sid = _session_with_media(client, tmp_path)
    r = client.post(f"/sessions/{sid}/transcribe")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    run_transcribe_job(job_id)
    job = client.get(f"/sessions/{sid}/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert job["kind"] == "transcribe"
    segs = client.get(f"/sessions/{sid}").json()["segments"]
    assert [s["speaker"] for s in segs] == ["interviewer", "candidate"]
    assert segs[0]["text"] == "Hello"


def test_run_job_marks_error_when_stt_fails(client, monkeypatch, tmp_path):
    def boom(path, hf_token=""):
        raise RuntimeError("whisper exploded")

    monkeypatch.setattr(stt_service, "transcribe_media", boom)
    sid = _session_with_media(client, tmp_path)
    job_id = db.create_job(sid, "transcribe")
    run_transcribe_job(job_id)
    job = client.get(f"/sessions/{sid}/jobs/{job_id}").json()
    assert job["status"] == "error"
    assert "whisper exploded" in job["error_message"]


def test_run_job_passes_hf_token_and_path(client, monkeypatch, tmp_path):
    seen = {}

    def spy(path, hf_token=""):
        seen["path"] = path
        seen["token"] = hf_token
        return FAKE_SEGMENTS

    monkeypatch.setattr(stt_service, "transcribe_media", spy)
    monkeypatch.setattr("app.config.HF_TOKEN", "tok123")
    sid = _session_with_media(client, tmp_path)
    job_id = db.create_job(sid, "transcribe")
    run_transcribe_job(job_id)
    assert str(seen["path"]).endswith("x.wav")
    assert seen["token"] == "tok123"


def test_transcribe_no_media_no_segments_is_400(client):
    sid = client.post("/sessions", json={"title": "T"}).json()["id"]
    assert client.post(f"/sessions/{sid}/transcribe").status_code == 400


def test_transcribe_paste_session_noops_to_done(client, monkeypatch):
    def fail(path, hf_token=""):
        raise AssertionError("STT must not run for paste sessions")

    monkeypatch.setattr(stt_service, "transcribe_media", fail)
    sid = client.post("/sessions", json={"title": "T"}).json()["id"]
    client.post(f"/sessions/{sid}/source/paste", json={"text": "Interviewer: Hi\nCandidate: Hello"})
    r = client.post(f"/sessions/{sid}/transcribe")
    assert r.status_code == 200
    job = client.get(f"/sessions/{sid}/jobs/{r.json()['job_id']}").json()
    assert job["status"] == "done"
    assert len(client.get(f"/sessions/{sid}").json()["segments"]) == 2


def test_transcribe_unknown_session_404(client):
    assert client.post("/sessions/nope/transcribe").status_code == 404


def test_get_job_404_and_wrong_session(client):
    s1 = client.post("/sessions", json={"title": "A"}).json()["id"]
    s2 = client.post("/sessions", json={"title": "B"}).json()["id"]
    job_id = db.create_job(s1, "transcribe")
    assert client.get(f"/sessions/{s1}/jobs/missing").status_code == 404
    assert client.get(f"/sessions/{s2}/jobs/{job_id}").status_code == 404
    assert client.get(f"/sessions/{s1}/jobs/{job_id}").status_code == 200


def test_patch_transcript(client):
    sid = client.post("/sessions", json={"title": "P"}).json()["id"]
    body = {
        "segments": [
            {"idx": 0, "start_ms": 0, "end_ms": 1, "speaker": "candidate", "text": "Edited"}
        ]
    }
    assert client.patch(f"/sessions/{sid}/transcript", json=body).status_code == 200
    assert client.get(f"/sessions/{sid}").json()["segments"][0]["text"] == "Edited"


def test_patch_transcript_replaces_all_and_validates(client):
    sid = client.post("/sessions", json={"title": "P"}).json()["id"]
    client.post(f"/sessions/{sid}/source/paste", json={"text": "Interviewer: Hi\nCandidate: Yo"})
    body = {"segments": [{"idx": 0, "speaker": "interviewer", "text": "Only"}]}
    assert client.patch(f"/sessions/{sid}/transcript", json=body).status_code == 200
    assert len(client.get(f"/sessions/{sid}").json()["segments"]) == 1
    bad = {"segments": [{"idx": 0, "speaker": "robot", "text": "x"}]}
    assert client.patch(f"/sessions/{sid}/transcript", json=bad).status_code == 422
    assert client.patch("/sessions/nope/transcript", json=body).status_code == 404


@pytest.mark.parametrize(
    "labels,expected",
    [
        ([], []),
        (
            ["A", "B", "A", "C"],
            ["interviewer", "candidate", "interviewer", "unknown"],
        ),
        (["X", "X"], ["interviewer", "interviewer"]),
        ([None, "A"], ["unknown", "interviewer"]),
    ],
)
def test_map_speakers(labels, expected):
    assert stt_service.map_speakers(labels) == expected


def test_stt_module_has_no_heavy_toplevel_imports():
    assert not hasattr(stt_service, "torch")
    assert not hasattr(stt_service, "WhisperModel")
