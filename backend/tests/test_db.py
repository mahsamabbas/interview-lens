from pathlib import Path

import app.config as config
from app import db


def test_init_and_create_session(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_PATH", tmp_path / "t.db")
    db.init_db()
    sid = db.create_session("Demo")
    row = db.get_session(sid)
    assert row["title"] == "Demo"
    assert row["status"] == "draft"
