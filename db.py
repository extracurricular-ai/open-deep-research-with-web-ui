"""
SQLite persistence layer for session history.

Stores sessions and their SSE events so users can replay past research runs.
Uses WAL mode for safe concurrent access from multiple Gunicorn workers.
"""

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "odr_sessions.db"

_local = threading.local()


def get_db_path():
    return os.environ.get("ODR_DB_PATH", str(DEFAULT_DB_PATH))


@contextmanager
def get_connection():
    """Thread-local SQLite connection with WAL mode."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(get_db_path(), timeout=10)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield _local.conn
    except Exception:
        _local.conn.rollback()
        raise


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                model_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                final_answer TEXT
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_order INTEGER NOT NULL,
                event_data TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_events_session
                ON events(session_id, event_order);

            CREATE INDEX IF NOT EXISTS idx_sessions_created
                ON sessions(created_at DESC);
        """)
        conn.commit()


def create_session(session_id, question, model_id):
    """Insert a new session row when streaming starts."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, question, model_id, status) VALUES (?, ?, ?, 'running')",
            (session_id, question, model_id),
        )
        conn.commit()


def append_event(session_id, event_order, event_data_dict):
    """Insert a single SSE event as it flows through the stream."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO events (session_id, event_order, event_data) VALUES (?, ?, ?)",
            (session_id, event_order, json.dumps(event_data_dict, default=str)),
        )
        conn.commit()


def complete_session(session_id, final_answer=None, status="completed"):
    """Mark a session as finished."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET completed_at = datetime('now'), status = ?, final_answer = ? WHERE id = ?",
            (status, final_answer, session_id),
        )
        conn.commit()


def list_sessions(limit=50, offset=0):
    """Return session summaries for the sidebar, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, question, model_id, created_at, completed_at, status,
                      SUBSTR(final_answer, 1, 200) as final_answer_preview
               FROM sessions
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def get_session(session_id):
    """Return a single session with all events for full replay."""
    with get_connection() as conn:
        session_row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session_row:
            return None

        events = conn.execute(
            "SELECT event_data FROM events WHERE session_id = ? ORDER BY event_order",
            (session_id,),
        ).fetchall()

        result = dict(session_row)
        result["events"] = [json.loads(row["event_data"]) for row in events]
        return result


def delete_session(session_id):
    """Delete a session and its events (CASCADE handles events)."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0
