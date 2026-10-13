import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from app import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  jd_text TEXT NOT NULL DEFAULT '',
  source_type TEXT,
  media_path TEXT
);
CREATE TABLE IF NOT EXISTS transcript_segments (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  idx INTEGER NOT NULL,
  start_ms INTEGER NOT NULL DEFAULT 0,
  end_ms INTEGER NOT NULL DEFAULT 0,
  speaker TEXT NOT NULL,
  text TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(id)
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  candidate_json TEXT NOT NULL,
  hiring_json TEXT NOT NULL,
  model_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_connection() -> sqlite3.Connection:
    path = config.SQLITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def create_session(title: str) -> str:
    sid = uuid4().hex
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, created_at, updated_at, status)
            VALUES (?, ?, ?, ?, 'draft')
            """,
            (sid, title, now, now),
        )
        conn.commit()
    return sid


def list_sessions() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at, updated_at, status, jd_text,
                   source_type, media_path
            FROM sessions
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, title, created_at, updated_at, status, jd_text,
                   source_type, media_path
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    return _row_to_dict(row)


def update_jd(session_id: str, jd_text: str) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sessions SET jd_text = ?, updated_at = ?
            WHERE id = ?
            """,
            (jd_text, now, session_id),
        )
        conn.commit()


def set_source(
    session_id: str,
    source_type: str,
    media_path: str | None = None,
) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET source_type = ?, media_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (source_type, media_path, now, session_id),
        )
        conn.commit()


def replace_segments(session_id: str, segments: list[dict]) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM transcript_segments WHERE session_id = ?",
            (session_id,),
        )
        for seg in segments:
            conn.execute(
                """
                INSERT INTO transcript_segments
                  (id, session_id, idx, start_ms, end_ms, speaker, text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    session_id,
                    seg["idx"],
                    seg.get("start_ms", 0),
                    seg.get("end_ms", 0),
                    seg["speaker"],
                    seg["text"],
                ),
            )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()


def list_segments(session_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, idx, start_ms, end_ms, speaker, text
            FROM transcript_segments
            WHERE session_id = ?
            ORDER BY idx ASC
            """,
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_job(session_id: str, kind: str, status: str = "queued") -> str:
    job_id = uuid4().hex
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, session_id, kind, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, session_id, kind, status, now, now),
        )
        conn.commit()
    return job_id


def update_job(
    job_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs SET status = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, error_message, now, job_id),
        )
        conn.commit()


def get_job(job_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, session_id, kind, status, error_message,
                   created_at, updated_at
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
    return _row_to_dict(row)


def save_report(
    session_id: str,
    candidate_json: dict,
    hiring_json: dict,
    model_name: str,
) -> str:
    report_id = uuid4().hex
    now = _utc_now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reports
              (id, session_id, candidate_json, hiring_json, model_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                session_id,
                json.dumps(candidate_json),
                json.dumps(hiring_json),
                model_name,
                now,
            ),
        )
        conn.commit()
    return report_id


def latest_report(session_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, session_id, candidate_json, hiring_json,
                   model_name, created_at
            FROM reports
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["candidate_json"] = json.loads(out["candidate_json"])
    out["hiring_json"] = json.loads(out["hiring_json"])
    return out
