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
        # isolation_level=None -> autocommit: each statement commits on its own,
        # and immediate_transaction() controls multi-statement atomicity with an
        # explicit BEGIN IMMEDIATE (no implicit-transaction surprises).
        _local.conn = sqlite3.connect(get_db_path(), timeout=10, isolation_level=None)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield _local.conn
    except Exception:
        _local.conn.rollback()
        raise


@contextmanager
def immediate_transaction():
    """Run a block inside a single ``BEGIN IMMEDIATE`` transaction.

    BEGIN IMMEDIATE takes SQLite's write lock up front, so the count-and-insert
    used by the concurrency gate is serialized across every Gunicorn worker —
    two workers cannot both observe spare capacity and both admit past the cap.
    Commits on success, rolls back on error.
    """
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
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
                final_answer TEXT,
                run_mode TEXT NOT NULL DEFAULT 'background',
                started_at TEXT,
                client_config TEXT
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

        # Migration: add run_mode column for existing databases
        try:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN run_mode TEXT NOT NULL DEFAULT 'background'"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: add concurrency-queue columns for existing databases.
        # started_at = when the session actually began running (vs created_at,
        # which is enqueue time); client_config = JSON overrides needed to
        # re-spawn a queued session when it is later promoted.
        for column_ddl in (
            "ALTER TABLE sessions ADD COLUMN started_at TEXT",
            "ALTER TABLE sessions ADD COLUMN client_config TEXT",
        ):
            try:
                conn.execute(column_ddl)
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists


def create_session(
    session_id,
    question,
    model_id,
    run_mode="background",
    status="running",
    client_config=None,
):
    """Insert a new session row.

    status defaults to 'running' (subprocess started immediately). started_at is
    stamped only when the row enters the 'running' state so the reaper can tell a
    genuinely-stuck run from one that was just promoted.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, question, model_id, status, run_mode, client_config, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ?='running' THEN datetime('now') ELSE NULL END)",
            (session_id, question, model_id, status, run_mode, client_config, status),
        )
        conn.commit()


def count_running():
    """Number of sessions currently in the 'running' state (the gate counter)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'running'"
        ).fetchone()[0]


def try_admit_or_queue(
    session_id, question, model_id, run_mode, client_config, max_concurrent
):
    """Atomically admit a new session as 'running' or buffer it as 'queued'.

    Counts running sessions and inserts the new row in one BEGIN IMMEDIATE
    transaction, so concurrent workers can never both admit past max_concurrent.
    Returns 'running' (caller should spawn the subprocess now) or 'queued'.
    """
    with immediate_transaction() as conn:
        running = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'running'"
        ).fetchone()[0]
        status = "running" if running < max_concurrent else "queued"
        conn.execute(
            "INSERT INTO sessions (id, question, model_id, status, run_mode, client_config, started_at) "
            "VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ?='running' THEN datetime('now') ELSE NULL END)",
            (session_id, question, model_id, status, run_mode, client_config, status),
        )
        return status


def promote_next_queued(max_concurrent):
    """Promote the oldest queued session to 'running' if capacity allows.

    Returns the promoted row as a dict (id, question, model_id, run_mode,
    client_config) so the caller can spawn its subprocess, or None when at
    capacity or the queue is empty. Atomic via BEGIN IMMEDIATE; FIFO by rowid
    (insertion order).
    """
    with immediate_transaction() as conn:
        running = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'running'"
        ).fetchone()[0]
        if running >= max_concurrent:
            return None
        row = conn.execute(
            "SELECT id, question, model_id, run_mode, client_config "
            "FROM sessions WHERE status = 'queued' ORDER BY rowid ASC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE sessions SET status = 'running', started_at = datetime('now') "
            "WHERE id = ? AND status = 'queued'",
            (row["id"],),
        )
        return dict(row)


def get_queue_position(session_id):
    """1-based FIFO position of a queued session, or None if it is not queued."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT rowid FROM sessions WHERE id = ? AND status = 'queued'",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'queued' AND rowid <= ?",
            (row["rowid"],),
        ).fetchone()[0]


def get_running_sessions():
    """Return [{id, started_at}] for every running session (for the reaper)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, started_at FROM sessions WHERE status = 'running'"
        ).fetchall()
        return [dict(r) for r in rows]


def fail_stale_session(session_id):
    """Mark a running session 'failed' to free its slot. No-op unless running."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET completed_at = datetime('now'), status = 'failed' "
            "WHERE id = ? AND status = 'running'",
            (session_id,),
        )
        return cursor.rowcount > 0


def cancel_queued_session(session_id):
    """Cancel a queued session (mark 'stopped'). Conditional on status='queued',
    so it loses cleanly to a concurrent promotion: returns True only if it was
    still queued, letting the caller fall back to the running-kill path."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET completed_at = datetime('now'), status = 'stopped' "
            "WHERE id = ? AND status = 'queued'",
            (session_id,),
        )
        return cursor.rowcount > 0


def append_event(session_id, event_order, event_data_dict):
    """Insert a single SSE event as it flows through the stream."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO events (session_id, event_order, event_data) VALUES (?, ?, ?)",
            (session_id, event_order, json.dumps(event_data_dict, default=str)),
        )
        conn.commit()


def complete_session(session_id, final_answer=None, status="completed"):
    """Mark a session finished — first terminal write wins.

    The WHERE clause only matches a still-in-flight ('running'/'queued') row, so
    a later 'completed' can never clobber a deliberate 'stopped'/'failed'/
    'interrupted' set by a stop, the reaper, or a client disconnect (and vice
    versa). Returns True if this call was the one that finalized the session."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET completed_at = datetime('now'), status = ?, final_answer = ? "
            "WHERE id = ? AND status IN ('running', 'queued')",
            (status, final_answer, session_id),
        )
        return cursor.rowcount > 0


def list_sessions(limit=50, offset=0):
    """Return session summaries for the sidebar, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, question, model_id, created_at, completed_at, status, run_mode,
                      SUBSTR(final_answer, 1, 200) as final_answer_preview
               FROM sessions
               ORDER BY created_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


def get_session(session_id):
    """Return a single session with all events for full replay.

    Explicit column allowlist (not SELECT *) so internal columns — client_config
    (may hold client-supplied provider keys) and started_at — are never exposed,
    and new columns are opt-in rather than auto-leaked."""
    with get_connection() as conn:
        session_row = conn.execute(
            "SELECT id, question, model_id, created_at, completed_at, status, "
            "run_mode, final_answer FROM sessions WHERE id = ?",
            (session_id,),
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


def get_events_after(session_id, after_order):
    """Return events with event_order > after_order for incremental polling."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT event_order, event_data FROM events WHERE session_id = ? AND event_order > ? ORDER BY event_order",
            (session_id, after_order),
        ).fetchall()
        return [
            {
                "event_order": row["event_order"],
                "event_data": json.loads(row["event_data"]),
            }
            for row in rows
        ]


def get_session_status(session_id):
    """Return just session status and run_mode (lightweight, for polling)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT status, run_mode FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


RESUMABLE_STATUSES = ("interrupted", "stopped", "failed")


def reopen_session_for_resume(session_id, max_concurrent):
    """Reopen a terminal session for warm-restart resume, respecting the gate.

    Atomically re-admits a resumable session through the same MAX_CONCURRENT gate
    as a fresh run: under capacity it goes straight to 'running' (the caller
    spawns now); at capacity it is re-queued and dispatch_pending() promotes it
    later, carrying the resume marker in client_config so the promoted run
    injects prior findings via --resume-session-id.

    Returns the new status ('running' or 'queued'), or None if the session was
    not in a resumable state (e.g. it lost the race to a concurrent transition).
    """
    placeholders = ", ".join("?" for _ in RESUMABLE_STATUSES)
    with immediate_transaction() as conn:
        row = conn.execute(
            f"SELECT client_config FROM sessions "
            f"WHERE id = ? AND status IN ({placeholders})",
            (session_id, *RESUMABLE_STATUSES),
        ).fetchone()
        if not row:
            return None

        running = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE status = 'running'"
        ).fetchone()[0]

        if running < max_concurrent:
            conn.execute(
                "UPDATE sessions SET status = 'running', completed_at = NULL, "
                "started_at = datetime('now') WHERE id = ?",
                (session_id,),
            )
            return "running"

        # At capacity: re-queue and stash the resume marker so dispatch_pending()
        # re-spawns this row with --resume-session-id when a slot frees.
        try:
            cfg = json.loads(row["client_config"]) if row["client_config"] else {}
            if not isinstance(cfg, dict):
                cfg = {}
        except (ValueError, TypeError):
            cfg = {}
        cfg["_resume_session_id"] = session_id
        conn.execute(
            "UPDATE sessions SET status = 'queued', completed_at = NULL, "
            "started_at = NULL, client_config = ? WHERE id = ?",
            (json.dumps(cfg), session_id),
        )
        return "queued"


def get_max_event_order(session_id):
    """Return the highest event_order for a session, or -1 if no events exist."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(event_order) as max_order FROM events WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        val = row["max_order"] if row else None
        return val if val is not None else -1


def get_session_for_resume(session_id):
    """Fetch session metadata needed for warm-restart resume.

    Returns None if the session doesn't exist or isn't in a resumable state. The
    event stream itself is intentionally NOT loaded here: the resumed run.py
    subprocess re-reads and extracts it via build_resume_context(), so parsing it
    on the request thread would be duplicated work that scales with history size.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT question, model_id, status, client_config FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row or row["status"] not in RESUMABLE_STATUSES:
            return None

        return {
            "question": row["question"],
            "model_id": row["model_id"],
            "status": row["status"],
            "client_config": row["client_config"],
        }
