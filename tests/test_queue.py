"""Tests for the SQLite-backed concurrency gate + buffered queue (db.py).

These cover the core back-pressure logic: admit-or-queue under a cap, FIFO
promotion, queue positions, slot reaping, and that the cap holds across
concurrent workers (the BEGIN IMMEDIATE invariant). client_config persistence /
non-leakage is checked too.
"""

import threading

import pytest

import db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Give each test its own empty SQLite file and a clean connection."""
    monkeypatch.setenv("ODR_DB_PATH", str(tmp_path / "test_sessions.db"))
    # Drop any cached thread-local connection so the new path takes effect.
    db._local.conn = None
    db.init_db()
    yield
    conn = getattr(db._local, "conn", None)
    if conn is not None:
        conn.close()
        db._local.conn = None


def admit(session_id, cap, run_mode="background", client_config=None):
    return db.try_admit_or_queue(
        session_id, "question", "model", run_mode, client_config, cap
    )


def test_admits_up_to_cap_then_queues():
    cap = 3
    decisions = [admit(f"s{i}", cap) for i in range(5)]
    assert decisions == ["running", "running", "running", "queued", "queued"]
    assert db.count_running() == 3


def test_queue_positions_are_fifo():
    cap = 1
    admit("run", cap)
    admit("a", cap)
    admit("b", cap)
    admit("c", cap)
    assert db.get_queue_position("a") == 1
    assert db.get_queue_position("b") == 2
    assert db.get_queue_position("c") == 3
    assert db.get_queue_position("run") is None  # running, not queued


def test_promote_is_fifo_and_respects_cap():
    cap = 1
    admit("run", cap)
    admit("a", cap)
    admit("b", cap)

    # At capacity: nothing promoted.
    assert db.promote_next_queued(cap) is None

    # Free the running slot, then the oldest queued (a) is promoted.
    db.complete_session("run", status="completed")
    promoted = db.promote_next_queued(cap)
    assert promoted is not None
    assert promoted["id"] == "a"
    assert db.get_queue_position("a") is None  # now running
    assert db.get_queue_position("b") == 1  # moved up

    # Back at capacity (a is running): b stays queued.
    assert db.promote_next_queued(cap) is None
    assert db.count_running() == 1


def test_promote_returns_fields_needed_to_respawn():
    cap = 1
    admit("run", cap)
    admit("q1", cap, run_mode="live", client_config='{"search": {"x": 1}}')
    db.complete_session("run", status="completed")

    promoted = db.promote_next_queued(cap)
    assert promoted["id"] == "q1"
    assert promoted["question"] == "question"
    assert promoted["model_id"] == "model"
    assert promoted["run_mode"] == "live"
    assert promoted["client_config"] == '{"search": {"x": 1}}'


def test_promote_returns_none_when_queue_empty():
    cap = 5
    admit("only", cap)
    assert db.promote_next_queued(cap) is None


def test_fail_stale_session_frees_slot_and_is_idempotent():
    cap = 1
    admit("run", cap)
    assert db.count_running() == 1
    assert db.fail_stale_session("run") is True
    assert db.count_running() == 0
    # Already failed -> no longer running -> no-op.
    assert db.fail_stale_session("run") is False


def test_get_running_sessions_reports_started_at():
    cap = 5
    admit("a", cap)
    admit("b", cap)
    running = db.get_running_sessions()
    ids = {r["id"] for r in running}
    assert ids == {"a", "b"}
    # Admitted-as-running rows get a started_at stamp for the reaper.
    assert all(r["started_at"] for r in running)


def test_queued_session_has_no_started_at_until_promoted():
    cap = 1
    admit("run", cap)
    admit("q1", cap)
    # Promote and confirm started_at is now stamped.
    db.complete_session("run", status="completed")
    db.promote_next_queued(cap)
    running = {r["id"]: r for r in db.get_running_sessions()}
    assert "q1" in running
    assert running["q1"]["started_at"]


def test_client_config_not_leaked_by_get_session():
    admit("s", 5, client_config='{"search": {"key": "secret"}}')
    session = db.get_session("s")
    assert session is not None
    assert "client_config" not in session
    # started_at is internal too — should not be exposed via the detail API.
    assert "started_at" not in session


def test_complete_session_first_terminal_write_wins():
    admit("s", 5)
    # First terminal write succeeds...
    assert db.complete_session("s", status="stopped") is True
    # ...a later 'completed' must NOT clobber the deliberate 'stopped'.
    assert db.complete_session("s", final_answer="x", status="completed") is False
    assert db.get_session("s")["status"] == "stopped"


def test_complete_session_can_finalize_a_queued_row():
    cap = 1
    admit("run", cap)
    admit("q", cap)
    # A queued row is still in-flight, so complete_session may finalize it.
    assert db.complete_session("q", status="stopped") is True
    assert db.get_session("q")["status"] == "stopped"


def test_cancel_queued_session_conditional_on_queued():
    cap = 1
    admit("run", cap)
    admit("q", cap)
    # Promote q -> running; a now-running row must NOT be cancellable as queued.
    db.complete_session("run", status="completed")
    db.promote_next_queued(cap)
    assert db.cancel_queued_session("q") is False
    assert db.get_session("q")["status"] == "running"


def test_cancel_queued_session_cancels_a_queued_row():
    cap = 1
    admit("run", cap)
    admit("q", cap)
    assert db.cancel_queued_session("q") is True
    assert db.get_session("q")["status"] == "stopped"
    assert db.count_running() == 1  # cancel did not touch the running slot


def test_gate_never_exceeds_cap_under_concurrency():
    """Many workers submitting at once must not collectively exceed the cap."""
    cap = 5
    n = 40
    results = {}
    barrier = threading.Barrier(n)

    def worker(i):
        # Each thread gets its own thread-local SQLite connection.
        barrier.wait()
        results[i] = admit(f"s{i}", cap)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    running = sum(1 for v in results.values() if v == "running")
    queued = sum(1 for v in results.values() if v == "queued")
    assert running == cap
    assert queued == n - cap
    assert db.count_running() == cap
