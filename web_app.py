import argparse
import os
import sys
import threading
import uuid
import signal
import subprocess
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    stream_with_context,
    Response,
)
from flask_cors import CORS

from db import (
    init_db,
    append_event,
    complete_session,
    list_sessions,
    get_session,
    delete_session as db_delete_session,
    get_events_after,
    get_session_status,
    try_admit_or_queue,
    promote_next_queued,
    get_queue_position,
    get_running_sessions,
    fail_stale_session,
    cancel_queued_session,
    get_session_for_resume,
    reopen_session_for_resume,
    get_max_event_order,
)
from config import load_config, save_config, _deep_merge

load_dotenv(override=True)

app = Flask(__name__, template_folder="templates")
CORS(app)

# Initialize session database (graceful degradation if it fails)
try:
    init_db()
except Exception as e:
    print(f"Warning: Failed to initialize database: {e}")

# Session tracking directory (shared across all workers)
SESSION_DIR = Path(tempfile.gettempdir()) / "open_deep_research_sessions"
SESSION_DIR.mkdir(exist_ok=True)

# Note: cleanup_stale_sessions() is called after function definitions below

# In-memory session tracking for this worker
# session_id -> {'process': subprocess.Popen, 'queue': Queue}
active_sessions: dict[str, dict] = {}
sessions_lock = threading.Lock()


def _parse_max_concurrent(default=16):
    """Max simultaneously-running research sessions, from ODR_MAX_CONCURRENT.

    Floor of 1 (a value < 1 would deadlock the queue — nothing could ever run);
    deliberately no upper cap, since the real ceiling is provider rate limits and
    memory, which the operator tunes for their own hardware.
    """
    try:
        return max(1, int(os.environ.get("ODR_MAX_CONCURRENT", str(default))))
    except (ValueError, TypeError):
        return default


MAX_CONCURRENT = _parse_max_concurrent()

# Background watchdog: re-checks the queue and reaps dead runs even if an
# event-driven dispatch tick was missed (e.g. a worker crashed mid-completion).
WATCHDOG_INTERVAL_SECONDS = 5.0
# A 'running' session with no session file is only reaped once it has been
# running longer than this — covers the tiny window between promotion (DB commit)
# and the subprocess/file actually being spawned.
REAP_GRACE_SECONDS = 30.0


def write_session_file(session_id, agent_pid, worker_pid, run_mode="background"):
    """Write session info to shared file atomically.

    Writes to a temp file then os.replace()s it into place, so a concurrent
    reader (the reaper) never observes a truncated/half-written JSON file."""
    session_file = SESSION_DIR / f"{session_id}.json"
    tmp_file = SESSION_DIR / f"{session_id}.json.{os.getpid()}.tmp"
    with open(tmp_file, "w") as f:
        json.dump(
            {
                "agent_pid": agent_pid,
                "worker_pid": worker_pid,
                "run_mode": run_mode,
                "created_at": time.time(),
            },
            f,
        )
    os.replace(tmp_file, session_file)


def read_session_file(session_id):
    """Read session info from shared file. Returns None if missing or corrupt
    (a partial write is treated as absent rather than raising)."""
    session_file = SESSION_DIR / f"{session_id}.json"
    try:
        with open(session_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return None


def delete_session_file(session_id):
    """Delete session file"""
    session_file = SESSION_DIR / f"{session_id}.json"
    if session_file.exists():
        session_file.unlink()


def read_process_output(process, queue, stderr_done_event):
    """Read JSON lines from process stdout and queue them.
    Waits for stderr thread to finish before sending end-of-stream,
    so any error captured from stderr is queued first."""
    try:
        for line in iter(process.stdout.readline, b""):
            if line:
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                    queue.put(event)
                except json.JSONDecodeError:
                    # Non-JSON line (library output that leaked to stdout)
                    queue.put({"type": "message", "content": text})
    except Exception as e:
        queue.put({"type": "error", "content": f"Error reading process output: {e}"})
    finally:
        # Wait for stderr thread to finish so errors are queued before end-of-stream
        stderr_done_event.wait(timeout=10)
        queue.put(None)  # Signal end of stream


def drain_stderr(process, queue, stderr_done_event):
    """Read stderr and capture it. Send errors to the queue so the client sees them."""
    stderr_lines = []
    try:
        for line in iter(process.stderr.readline, b""):
            if line:
                text = line.decode("utf-8", errors="replace").rstrip()
                print(f"[agent] {text}")
                stderr_lines.append(text)
    except Exception:
        pass
    finally:
        # After stderr closes, check if process failed
        process.wait()
        rc = process.returncode
        # Only report errors for genuine failures, not when killed by signal (negative rc)
        if rc and rc > 0:
            error_msg = (
                "\n".join(stderr_lines[-20:])
                if stderr_lines
                else f"Agent process exited with code {rc}"
            )
            queue.put({"type": "error", "content": error_msg})
        stderr_done_event.set()


def background_worker(session_id, output_queue, process):
    """Read subprocess output and persist to DB, independent of any HTTP connection.
    Runs in a daemon thread. Cleans up session file when subprocess ends."""
    event_counter = get_max_event_order(session_id) + 1
    session_final_answer = None

    try:
        while True:
            item = output_queue.get()
            if item is None:  # End of stream
                break

            try:
                append_event(session_id, event_counter, item)
                event_counter += 1
            except Exception as db_err:
                print(f"DB: Failed to append event: {db_err}")

            if item.get("type") == "final_answer" and not item.get("agent_name"):
                session_final_answer = (item.get("output") or item.get("content", ""))[
                    :5000
                ]

    except Exception as e:
        print(f"Background worker error for {session_id}: {e}")
    finally:
        with sessions_lock:
            if session_id in active_sessions:
                del active_sessions[session_id]
        delete_session_file(session_id)

        try:
            # Only mark completed if not already stopped/interrupted
            status_info = get_session_status(session_id)
            if status_info and status_info["status"] == "running":
                # A crash is a non-zero exit with no final answer; otherwise the
                # run completed (with or without an answer).
                rc = process.returncode
                if not session_final_answer and rc and rc != 0:
                    complete_session(session_id, status="failed")
                else:
                    complete_session(
                        session_id, final_answer=session_final_answer, status="completed"
                    )
        except Exception:
            pass

        # Slot freed — promote the next queued session if any.
        dispatch_pending()


def _pid_alive(pid):
    """True if pid is a live process. PermissionError means it exists but we may
    not signal it — still alive. Non-int/None -> not alive."""
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _kill_agent(agent_pid):
    """Best-effort SIGKILL of an agent subprocess by PID."""
    if not isinstance(agent_pid, int):
        return
    try:
        os.kill(agent_pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _running_longer_than(started_at, seconds):
    """True if started_at (UTC 'YYYY-MM-DD HH:MM:SS' from SQLite datetime('now'))
    is older than the grace window. Missing/unparseable -> True (treat as stale).
    A backward clock jump (negative elapsed) counts as within-grace so a freshly
    promoted session is never falsely reaped."""
    if not started_at:
        return True
    try:
        started = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return True
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    if elapsed < 0:
        return False
    return elapsed > seconds


def cleanup_stale_sessions():
    """On startup, reconcile leftover session files. A file whose OWNING WORKER
    is dead is from a previous run -> kill any surviving agent, mark the session
    interrupted, and remove the file. Files of still-alive workers (sibling
    workers in a multi-worker deploy) are left untouched. Corrupt files are just
    unlinked."""
    try:
        for session_file in SESSION_DIR.glob("*.json"):
            session_id = session_file.stem
            try:
                data = read_session_file(session_id)
                if data is None:
                    session_file.unlink(missing_ok=True)
                    continue
                if _pid_alive(data.get("worker_pid")):
                    continue  # owning worker alive -> live session, keep
                _kill_agent(data.get("agent_pid"))
                try:
                    complete_session(session_id, status="interrupted")
                except Exception:
                    pass
                session_file.unlink(missing_ok=True)
            except Exception:
                session_file.unlink(missing_ok=True)
    except Exception as e:
        print(f"Startup cleanup error: {e}")


def reap_dead_sessions():
    """Free slots held by running sessions whose owning worker is gone.

    Each session's owning worker (worker_pid in its session file) is responsible
    for draining its output and finalizing it, so:
      - file present + owning worker ALIVE -> healthy; skip (that worker finalizes).
      - file present + owning worker DEAD  -> orphaned: kill the agent if still
        alive (nobody is draining it), mark 'failed', free the slot.
      - no file + 'running' past the grace window -> promoted but the subprocess
        never came up (or died before writing the file) -> mark 'failed'.
    Keying on the WORKER pid (not the agent pid) avoids both false-reaping a
    still-finishing run and the agent-PID-reuse slot leak. One bad session never
    aborts the sweep. Returns count reaped."""
    reaped = 0
    try:
        running = get_running_sessions()
    except Exception as e:
        print(f"Reaper: failed to list running sessions: {e}")
        return 0

    for sess in running:
        session_id = sess["id"]
        try:
            data = read_session_file(session_id)
            if data is not None:
                if _pid_alive(data.get("worker_pid")):
                    continue  # owning worker alive -> it will finalize
                # Owning worker dead -> orphaned run; stop the agent too.
                _kill_agent(data.get("agent_pid"))
            elif not _running_longer_than(sess.get("started_at"), REAP_GRACE_SECONDS):
                continue  # no file yet, but still within the spawn grace window

            if fail_stale_session(session_id):
                reaped += 1
                with sessions_lock:
                    active_sessions.pop(session_id, None)
                delete_session_file(session_id)
        except Exception as e:
            print(f"Reaper: failed to reap {session_id}: {e}")

    return reaped


def watchdog_loop():
    """Fallback dispatcher + reaper. Each worker runs one; promotion and reaping
    are atomic in SQLite, so multiple concurrent watchdogs are safe."""
    # Small per-worker stagger so workers don't all contend the write lock at once.
    time.sleep((os.getpid() % 1000) / 1000.0)
    while True:
        time.sleep(WATCHDOG_INTERVAL_SECONDS)
        try:
            reaped = reap_dead_sessions()
            if reaped:
                print(f"Watchdog: reaped {reaped} dead session(s)")
            dispatch_pending()
        except Exception as e:
            print(f"Watchdog error: {e}")


_watchdog_started = False
_watchdog_lock = threading.Lock()


def start_watchdog():
    """Start the watchdog thread once per worker process."""
    global _watchdog_started
    with _watchdog_lock:
        if _watchdog_started:
            return
        _watchdog_started = True
    threading.Thread(target=watchdog_loop, daemon=True).start()


# Background tasks can be disabled (tests / embedding) so importing this module
# has no side effects on the DB and no timing races against the watchdog.
_BACKGROUND_DISABLED = os.environ.get("ODR_DISABLE_BACKGROUND") == "1"

if not _BACKGROUND_DISABLED:
    # Clean up any stale sessions from previous runs (orphaned session files),
    # then authoritatively reap 'running' DB rows whose owning worker is gone so
    # a restart never starts with phantom slots consumed.
    try:
        cleanup_stale_sessions()
        reap_dead_sessions()
    except Exception as e:
        print(f"Warning: Failed to clean up stale sessions: {e}")

    # Start the background queue watchdog (reaps dead runs, promotes queued ones).
    try:
        start_watchdog()
    except Exception as e:
        print(f"Warning: Failed to start watchdog: {e}")


@app.route("/")
def index():
    """Serve the main HTML page"""
    return render_template("index.html")


def build_config_json(model_id, client_config):
    """Merge server config + selected model + client overrides into the JSON
    blob run.py consumes. Mirrors the original inline merge; models are dropped
    from client overrides because they are admin-only."""
    server_cfg = load_config()
    override = {"model": {"default_model_id": model_id}}
    if client_config:
        client_config = dict(client_config)
        client_config.pop("models", None)
        override = _deep_merge(override, client_config)
    return json.dumps(_deep_merge(server_cfg, override))


def spawn_session(session_id, question, model_id, run_mode, client_config, resume_session_id=None):
    """Start the agent subprocess for a session whose DB row is already 'running'.

    Launches run.py, registers the process in this worker's active_sessions and
    the shared session file, and starts the stdout/stderr reader threads plus a
    background_worker daemon that drains output to the DB. The daemon is the
    SOLE queue consumer for EVERY mode (background, coupled live/auto-kill, and
    queue-promoted), so a session is always persisted and finalized even if no
    HTTP connection is reading it — coupled requests stream from the DB instead.
    Returns (process, output_queue)."""
    config_json_str = build_config_json(model_id, client_config)
    output_queue: Queue = Queue()

    env = os.environ.copy()
    cmd = [sys.executable, "-u", "run.py", question, "--config-json", config_json_str]
    if resume_session_id:
        cmd.extend(["--resume-session-id", resume_session_id])
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        bufsize=1,
    )

    # Shared file lets any worker find/stop this run; in-memory dict is local.
    write_session_file(session_id, process.pid, os.getpid(), run_mode)
    with sessions_lock:
        active_sessions[session_id] = {"process": process, "queue": output_queue}

    stderr_done = threading.Event()
    threading.Thread(
        target=read_process_output,
        args=(process, output_queue, stderr_done),
        daemon=True,
    ).start()
    threading.Thread(
        target=drain_stderr,
        args=(process, output_queue, stderr_done),
        daemon=True,
    ).start()

    threading.Thread(
        target=background_worker,
        args=(session_id, output_queue, process),
        daemon=True,
    ).start()

    return process, output_queue


def dispatch_pending():
    """Promote queued sessions to running while capacity allows, spawning each as
    a detached background run. Safe to call from any worker/thread: the actual
    promotion is atomic in SQLite, so concurrent dispatchers never exceed the cap
    or double-start a row."""
    try:
        while True:
            row = promote_next_queued(MAX_CONCURRENT)
            if not row:
                break
            client_config = None
            if row.get("client_config"):
                try:
                    client_config = json.loads(row["client_config"])
                except (ValueError, TypeError):
                    client_config = None
            resume_session_id = None
            if client_config and "_resume_session_id" in client_config:
                resume_session_id = client_config.pop("_resume_session_id")
            try:
                spawn_session(
                    row["id"],
                    row["question"],
                    row["model_id"],
                    row["run_mode"] or "background",
                    client_config,
                    resume_session_id=resume_session_id,
                )
            except Exception as spawn_err:
                print(f"Dispatch: failed to spawn {row['id']}: {spawn_err}")
                # Release the slot we just claimed so the queue keeps moving.
                try:
                    fail_stale_session(row["id"])
                except Exception:
                    pass
    except Exception as e:
        print(f"Dispatch error: {e}")


@app.route("/api/run/stream", methods=["POST"])
def run_agent_stream():
    """Streaming API endpoint using Server-Sent Events.
    Supports run_mode: 'background' (default), 'auto-kill', 'live'.

    Submissions pass through a global concurrency gate: under MAX_CONCURRENT
    running sessions the subprocess starts immediately, otherwise the session is
    buffered as 'queued' (no subprocess) and the client watches it via
    /api/sessions/<id>/live until the dispatcher promotes it. The gate lives in
    SQLite so it holds across every Gunicorn worker."""
    try:
        data = request.json
        question = data.get("question", "").strip()
        model_id = data.get("model_id", "o1")
        run_mode = data.get("run_mode", "background")
        client_config = data.get("client_config", {}) or {}

        if run_mode not in ("background", "auto-kill", "live"):
            run_mode = "background"

        if not question:
            return jsonify({"error": "Question is required"}), 400

        session_id = str(uuid.uuid4())

        # Persist client overrides (minus admin-only models) so a queued session
        # can be re-spawned by any worker when promoted. Often empty for default
        # runs — stored as NULL then.
        client_config = dict(client_config)
        client_config.pop("models", None)
        client_config_json = json.dumps(client_config) if client_config else None

        # Atomic admit-or-queue, enforced globally across workers.
        try:
            decision = try_admit_or_queue(
                session_id,
                question,
                model_id,
                run_mode,
                client_config_json,
                MAX_CONCURRENT,
            )
        except Exception as db_err:
            print(f"DB: Failed to create session: {db_err}")
            return jsonify({"error": "Failed to create session"}), 500

        if decision == "queued":
            # None if it was promoted in the gap before this read; omit position
            # then (the client shows a generic "Queued…" until /live corrects it).
            position = get_queue_position(session_id)
            queued_payload = {"session_id": session_id, "status": "queued"}
            if position and position > 0:
                queued_payload["position"] = position

            def generate_queued():
                yield "data: " + json.dumps(queued_payload) + "\n\n"

            return Response(
                stream_with_context(generate_queued()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        # Admitted — start the subprocess now. spawn_session attaches the
        # background drainer that persists output + finalizes the session for
        # EVERY mode, so the run is never stranded by a missing/dead reader.
        try:
            spawn_session(session_id, question, model_id, run_mode, client_config)
        except Exception as spawn_err:
            print(f"Failed to spawn session {session_id}: {spawn_err}")
            try:
                fail_stale_session(session_id)
            finally:
                dispatch_pending()
            return jsonify({"error": str(spawn_err)}), 500

        if run_mode == "background":
            # Background persistent: client connects to /api/sessions/<id>/live.
            def generate_background():
                yield (
                    "data: "
                    + json.dumps({"session_id": session_id, "status": "running"})
                    + "\n\n"
                )

            return Response(
                stream_with_context(generate_background()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        # Coupled (auto-kill / live): stream the run from the DB over this
        # request (the drainer owns persistence), and kill the agent if the
        # client disconnects. Because finalization belongs to the drainer,
        # abandoning or losing this connection cannot strand the run or its slot.
        def generate():
            after_order = -1
            try:
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"
                while True:
                    new_events = get_events_after(session_id, after_order)
                    for evt_row in new_events:
                        yield f"data: {json.dumps(evt_row['event_data'])}\n\n"
                        after_order = evt_row["event_order"]

                    status_info = get_session_status(session_id)
                    status = status_info["status"] if status_info else None
                    if status != "running":
                        yield f"data: {json.dumps({'done': True, 'status': status})}\n\n"
                        return

                    # Heartbeat so a client disconnect surfaces as GeneratorExit.
                    yield ": heartbeat\n\n"
                    time.sleep(0.5)

            except GeneratorExit:
                # Client disconnected — auto-kill the agent; the drainer will
                # observe the dead subprocess and finalize + dispatch.
                print(f"Client disconnected for session {session_id}, killing agent...")
                with sessions_lock:
                    sess = active_sessions.get(session_id)
                proc = sess.get("process") if sess else None
                if proc and proc.poll() is None:
                    try:
                        proc.kill()
                        proc.wait(timeout=1)
                    except Exception:
                        pass
                complete_session(session_id, status="interrupted")
                dispatch_pending()
                raise

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop/<session_id>", methods=["POST"])
def stop_session(session_id):
    """Stop a running agent session. Mode-aware: auto-kill also kills the worker."""
    try:
        # No subprocess on disk yet? It may be a queued session (cancel = DB
        # transition only, no process to kill). cancel_queued_session is
        # conditional on status='queued', so if it was promoted in the gap we
        # fall through to the normal kill path below.
        session_data = read_session_file(session_id)
        if not session_data:
            if cancel_queued_session(session_id):
                dispatch_pending()
                return (
                    jsonify({"success": True, "message": "Queued session cancelled"}),
                    200,
                )
            # Not queued — re-read the file in case it was just promoted+spawned.
            session_data = read_session_file(session_id)
            if not session_data:
                return jsonify({"success": False, "message": "Session not found"}), 404

        agent_pid = session_data["agent_pid"]
        run_mode = session_data.get("run_mode", "background")

        # Mark session as stopped in DB before killing processes
        try:
            complete_session(session_id, status="stopped")
        except Exception:
            pass

        # Kill the agent subprocess
        try:
            os.kill(agent_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Already dead

        # For coupled modes (auto-kill, live), unblock generate() by injecting
        # None into the output queue (if this is our worker)
        if run_mode in ("auto-kill", "live"):
            with sessions_lock:
                if session_id in active_sessions:
                    try:
                        active_sessions[session_id]["queue"].put(None)
                    except Exception:
                        pass
        # Background: background_worker thread will notice the process died and clean up.

        # Cleanup session file
        delete_session_file(session_id)

        # Slot freed — promote the next queued session if any.
        dispatch_pending()

        return jsonify({"success": True, "message": "Agent terminated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/models", methods=["GET"])
def get_models():
    """Return list of available models from config"""
    cfg = load_config()
    return jsonify(cfg.get("models", []))


@app.route("/api/models/discover", methods=["POST"])
def discover_models():
    """Discover available models from configured providers.

    Accepts optional client-supplied providers list in request body:
      { "providers": [{"provider": "openai", "api_key": "sk-...", "base_url": ""},  ...] }

    Merges client providers with server config providers (client takes precedence).
    Queries:
      - OpenAI-compatible /v1/models for: openai, deepseek, and any provider with base_url
      - Ollama /api/tags for: ollama provider

    Returns:
      { "discovered": [{"id": "...", "provider": "..."}], "errors": [...] }
    """
    import urllib.request
    import urllib.error

    data = request.json or {}
    client_providers = data.get("providers", [])

    # Build merged provider map: server config as base, client overrides on top
    server_cfg = load_config()
    server_providers = server_cfg.get("model", {}).get("providers", [])

    # Index by provider name (case-insensitive)
    merged = {}
    for p in server_providers:
        key = p.get("provider", "").lower()
        if key:
            merged[key] = dict(p)
    for p in client_providers:
        key = p.get("provider", "").lower()
        if key:
            existing = merged.get(key, {})
            merged[key] = {**existing, **{k: v for k, v in p.items() if v}}

    discovered = []
    errors = []

    OPENAI_COMPATIBLE = {"openai", "deepseek"}

    for provider_key, pinfo in merged.items():
        api_key = pinfo.get("api_key", "")
        base_url = (pinfo.get("base_url") or "").rstrip("/")

        if provider_key == "ollama":
            # Ollama uses /api/tags
            url = (base_url or "http://localhost:11434") + "/api/tags"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ODR/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    body = json.loads(resp.read())
                models_list = body.get("models", [])
                for m in models_list:
                    name = m.get("name") or m.get("model", "")
                    if name:
                        discovered.append(
                            {"id": f"ollama/{name}", "provider": "ollama"}
                        )
            except Exception as e:
                errors.append(f"ollama: {str(e)}")

        elif provider_key == "anthropic":
            # Anthropic /v1/models endpoint (uses x-api-key, not Bearer)
            if not api_key:
                continue
            url = (base_url or "https://api.anthropic.com") + "/v1/models"
            headers = {
                "User-Agent": "ODR/1.0",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            }
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    body = json.loads(resp.read())
                models_list = body.get("data", [])
                for m in models_list:
                    model_id = m.get("id", "")
                    if model_id:
                        discovered.append({"id": model_id, "provider": "anthropic"})
            except Exception as e:
                errors.append(f"anthropic: {str(e)}")

        elif provider_key in OPENAI_COMPATIBLE or base_url:
            # OpenAI-compatible /v1/models
            if not api_key and not base_url:
                continue  # No credentials, skip
            endpoint_base = (
                base_url
                if base_url
                else {
                    "openai": "https://api.openai.com",
                    "deepseek": "https://api.deepseek.com",
                }.get(provider_key, "")
            )
            if not endpoint_base:
                continue
            url = endpoint_base + "/v1/models"
            headers = {"User-Agent": "ODR/1.0"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    body = json.loads(resp.read())
                models_list = body.get("data", [])
                for m in models_list:
                    model_id = m.get("id", "")
                    if model_id:
                        # Prefix non-openai providers
                        full_id = (
                            model_id
                            if provider_key == "openai"
                            else f"{provider_key}/{model_id}"
                        )
                        discovered.append({"id": full_id, "provider": provider_key})
            except Exception as e:
                errors.append(f"{provider_key}: {str(e)}")

    return jsonify({"discovered": discovered, "errors": errors})


# ===== Config API =====


def _mask_api_key(key):
    """Mask an API key for display: 'sk-abc123xyz' -> 'sk-***xyz'"""
    if not key or len(key) < 6:
        return key
    return key[:3] + "***" + key[-3:]


@app.route("/api/config/meta", methods=["GET"])
def config_meta():
    """Return config UI metadata (no auth required)"""
    enable_ui = os.getenv("ENABLE_CONFIG_UI", "false").lower() in ("true", "1", "yes")
    return jsonify({"enable_config_ui": enable_ui})


def _check_admin_password(password):
    """Validate admin password against env var."""
    admin_password = os.getenv("CONFIG_ADMIN_PASSWORD", "")
    return admin_password and password == admin_password


@app.route("/api/config/verify", methods=["POST"])
def verify_admin_password():
    """Verify admin password without changing anything"""
    enable_ui = os.getenv("ENABLE_CONFIG_UI", "false").lower() in ("true", "1", "yes")
    if not enable_ui:
        return jsonify({"error": "Config UI is disabled"}), 403

    data = request.json
    password = data.get("password", "")
    if _check_admin_password(password):
        return jsonify({"valid": True})
    return jsonify({"valid": False}), 401


@app.route("/api/config", methods=["GET"])
def get_config_endpoint():
    """Return server config with API keys masked. Requires admin password."""
    enable_ui = os.getenv("ENABLE_CONFIG_UI", "false").lower() in ("true", "1", "yes")
    if not enable_ui:
        return jsonify({"error": "Config UI is disabled"}), 403

    password = request.headers.get("X-Admin-Password", "")
    if not _check_admin_password(password):
        return jsonify({"error": "Invalid admin password"}), 401

    cfg = load_config()
    # Mask sensitive keys for display
    for p in cfg.get("model", {}).get("providers", []):
        if p.get("api_key"):
            p["api_key"] = _mask_api_key(p["api_key"])
    for p in cfg.get("search", {}).get("providers", []):
        if p.get("key"):
            p["key"] = _mask_api_key(p["key"])
    for k, v in cfg.get("other_keys", {}).items():
        if v:
            cfg["other_keys"][k] = _mask_api_key(v)
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def update_config_endpoint():
    """Update server config (requires admin password when ENABLE_CONFIG_UI is true)"""
    enable_ui = os.getenv("ENABLE_CONFIG_UI", "false").lower() in ("true", "1", "yes")
    if not enable_ui:
        return jsonify({"error": "Config UI is disabled"}), 403

    data = request.json
    password = data.get("_password", "")

    if not _check_admin_password(password):
        return jsonify({"error": "Invalid admin password"}), 401

    # Remove password and legacy api_keys from config data before saving
    config_data = {k: v for k, v in data.items() if k not in ("_password", "api_keys")}

    # Merge with existing config (so partial updates work)
    current = load_config()
    merged = _deep_merge(current, config_data)

    # Preserve original keys when masked values (containing '***') are sent back
    for i, p in enumerate(merged.get("model", {}).get("providers", [])):
        if "***" in (p.get("api_key") or ""):
            orig = current.get("model", {}).get("providers", [])
            if i < len(orig):
                p["api_key"] = orig[i].get("api_key", "")
    for i, p in enumerate(merged.get("search", {}).get("providers", [])):
        if "***" in (p.get("key") or ""):
            orig = current.get("search", {}).get("providers", [])
            if i < len(orig):
                p["key"] = orig[i].get("key", "")
    for k, v in merged.get("other_keys", {}).items():
        if "***" in (v or ""):
            merged["other_keys"][k] = current.get("other_keys", {}).get(k, "")

    save_config(merged)

    return jsonify({"success": True})


# ===== Session History API =====


@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """Return paginated session list for sidebar"""
    try:
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        sessions = list_sessions(limit=min(limit, 100), offset=offset)
        return jsonify(sessions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>", methods=["GET"])
def api_get_session(session_id):
    """Return a single session with all events for replay"""
    try:
        session = get_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        # Surface queue position so the client can render "Queued (position N)".
        if session.get("status") == "queued":
            session["queue_position"] = get_queue_position(session_id)
        return jsonify(session)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/live")
def session_live_stream(session_id):
    """SSE stream: replay existing events from DB, then poll for new ones.
    Used for reconnecting to background sessions."""
    after_order = request.args.get("after_order", -1, type=int)

    def generate_live():
        nonlocal after_order

        # Send session_id first
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        last_position = None
        while True:
            status_info = get_session_status(session_id)
            if not status_info:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Session not found'})}\n\n"
                return

            status = status_info["status"]

            # Queued: no subprocess yet. Report queue position and keep waiting
            # until the dispatcher promotes this session to 'running'.
            if status == "queued":
                position = get_queue_position(session_id)
                if position != last_position:
                    last_position = position
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "type": "queue_status",
                                "status": "queued",
                                "position": position,
                            }
                        )
                        + "\n\n"
                    )
                time.sleep(1.0)
                continue

            # Running or finished: stream any new events since after_order.
            new_events = get_events_after(session_id, after_order)
            for evt_row in new_events:
                yield f"data: {json.dumps(evt_row['event_data'])}\n\n"
                after_order = evt_row["event_order"]

            # Terminal status (completed / interrupted / stopped / failed): done.
            # Carry the status so the client renders failed/stopped distinctly
            # instead of a blanket "Completed successfully".
            if status != "running":
                yield f"data: {json.dumps({'done': True, 'status': status})}\n\n"
                return

            time.sleep(0.5)

    return Response(
        stream_with_context(generate_live()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """Delete a session and its events. If it is still in flight, tear it down
    first (kill subprocess / cancel queue slot) so deleting a live row cannot
    orphan its agent or strip its slot from the gate without freeing it."""
    try:
        status_info = get_session_status(session_id)
        in_flight = status_info and status_info["status"] in ("running", "queued")
        if in_flight:
            try:
                stop_session(session_id)  # kills agent / cancels queue + dispatches
            except Exception as stop_err:
                print(f"Delete: failed to stop {session_id} before delete: {stop_err}")

        deleted = db_delete_session(session_id)
        if not deleted:
            return jsonify({"error": "Session not found"}), 404

        if in_flight:
            dispatch_pending()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/resume", methods=["POST"])
def api_resume_session(session_id):
    """Resume a failed/interrupted/stopped session via warm restart.

    Reopens the same session and spawns a new agent run that injects prior
    findings as context, continuing research without repeating completed work.
    Admission goes through the same MAX_CONCURRENT gate as a normal run: at
    capacity the session is re-queued and promoted by the dispatcher later."""
    try:
        original = get_session_for_resume(session_id)
        if not original:
            return jsonify({"error": "Session not found or not in a resumable state"}), 400

        decision = reopen_session_for_resume(session_id, MAX_CONCURRENT)
        if decision is None:
            return jsonify({"error": "Session could not be reopened (status may have changed)"}), 409

        # At capacity: the row is now 'queued' with the resume marker persisted;
        # dispatch_pending() will spawn it (with --resume-session-id) when a slot
        # frees. Nothing to launch right now.
        if decision == "queued":
            return jsonify({"session_id": session_id, "status": "queued"})

        question = original["question"]
        model_id = original["model_id"]
        client_config = None
        if original.get("client_config"):
            try:
                client_config = json.loads(original["client_config"])
            except (json.JSONDecodeError, TypeError):
                pass

        run_mode = "background"
        try:
            spawn_session(
                session_id, question, model_id, run_mode, client_config,
                resume_session_id=session_id,
            )
        except Exception as spawn_err:
            # Release the slot we just claimed so the gate/queue stay correct,
            # mirroring dispatch_pending()'s spawn-failure handling.
            try:
                fail_stale_session(session_id)
                dispatch_pending()
            except Exception:
                pass
            return jsonify({"error": f"Failed to start resume: {spawn_err}"}), 500

        return jsonify({"session_id": session_id, "status": "running"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5080)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--debug", type=bool, default=True)
    args = parser.parse_args()

    print(f"Starting web UI at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
