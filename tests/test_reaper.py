"""Tests for the slot reaper and startup recovery (web_app.py).

The reaper keys on the OWNING WORKER pid, not the agent pid: a session is healthy
only while the worker that spawned it is alive. These tests exercise that logic
plus the spawn grace window and startup file reconciliation, using a real
dead pid (a child we spawn and wait on) so liveness checks are genuine.
"""

import os
import subprocess
import sys

import pytest

import db
import web_app


@pytest.fixture
def reaper_env(tmp_path, monkeypatch):
    """Isolated DB + SESSION_DIR so the reaper never touches real state."""
    monkeypatch.setenv("ODR_DB_PATH", str(tmp_path / "reaper.db"))
    db._local.conn = None
    db.init_db()

    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    monkeypatch.setattr(web_app, "SESSION_DIR", session_dir)
    yield
    conn = getattr(db._local, "conn", None)
    if conn is not None:
        conn.close()
        db._local.conn = None


def _dead_pid():
    """A pid that is definitely not alive (child spawned then reaped)."""
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def _make_running(session_id):
    db.create_session(session_id, "q", "m", status="running")


def _set_started_at(session_id, value):
    with db.get_connection() as conn:
        conn.execute(
            "UPDATE sessions SET started_at = ? WHERE id = ?", (value, session_id)
        )


def test_healthy_session_with_live_worker_is_not_reaped(reaper_env):
    _make_running("s")
    # Owning worker = this live test process -> healthy.
    web_app.write_session_file("s", agent_pid=_dead_pid(), worker_pid=os.getpid())
    assert web_app.reap_dead_sessions() == 0
    assert db.get_session_status("s")["status"] == "running"


def test_session_with_dead_worker_is_reaped(reaper_env):
    _make_running("s")
    web_app.write_session_file("s", agent_pid=_dead_pid(), worker_pid=_dead_pid())
    assert web_app.reap_dead_sessions() == 1
    assert db.get_session_status("s")["status"] == "failed"
    # Slot freed and the stale file removed.
    assert db.count_running() == 0
    assert web_app.read_session_file("s") is None


def test_fileless_running_past_grace_is_reaped(reaper_env):
    _make_running("s")
    _set_started_at("s", "2000-01-01 00:00:00")  # far past the grace window
    assert web_app.reap_dead_sessions() == 1
    assert db.get_session_status("s")["status"] == "failed"


def test_fileless_running_within_grace_is_not_reaped(reaper_env):
    _make_running("s")  # started_at = now -> within REAP_GRACE_SECONDS
    assert web_app.reap_dead_sessions() == 0
    assert db.get_session_status("s")["status"] == "running"


def test_one_corrupt_file_does_not_abort_the_sweep(reaper_env):
    # A genuinely dead session that should be reaped...
    _make_running("dead")
    web_app.write_session_file("dead", agent_pid=_dead_pid(), worker_pid=_dead_pid())
    # ...and a corrupt session file ordered alongside it.
    _make_running("corrupt")
    (web_app.SESSION_DIR / "corrupt.json").write_text("{ not valid json")

    reaped = web_app.reap_dead_sessions()  # must not raise
    # The dead one is still reaped despite the corrupt neighbour.
    assert db.get_session_status("dead")["status"] == "failed"
    assert reaped >= 1


def test_cleanup_stale_sessions_reconciles_by_worker_liveness(reaper_env):
    # Previous-run session: owning worker dead -> interrupted + file removed.
    _make_running("old")
    web_app.write_session_file("old", agent_pid=_dead_pid(), worker_pid=_dead_pid())
    # Live sibling session: owning worker alive -> left untouched.
    _make_running("live")
    web_app.write_session_file("live", agent_pid=_dead_pid(), worker_pid=os.getpid())

    web_app.cleanup_stale_sessions()

    assert db.get_session_status("old")["status"] == "interrupted"
    assert web_app.read_session_file("old") is None
    assert db.get_session_status("live")["status"] == "running"
    assert web_app.read_session_file("live") is not None
