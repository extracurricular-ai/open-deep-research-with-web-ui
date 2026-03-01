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
from pathlib import Path
from queue import Queue

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, stream_with_context, Response
from flask_cors import CORS

from db import (
    init_db, create_session as db_create_session, append_event,
    complete_session, list_sessions, get_session, delete_session as db_delete_session,
    get_events_after, get_session_status,
)

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
active_sessions = {}  # session_id -> {'process': subprocess.Popen, 'queue': Queue}
sessions_lock = threading.Lock()


def write_session_file(session_id, agent_pid, worker_pid, run_mode='background'):
    """Write session info to shared file"""
    session_file = SESSION_DIR / f"{session_id}.json"
    with open(session_file, 'w') as f:
        json.dump({
            'agent_pid': agent_pid,
            'worker_pid': worker_pid,
            'run_mode': run_mode,
            'created_at': time.time()
        }, f)


def read_session_file(session_id):
    """Read session info from shared file"""
    session_file = SESSION_DIR / f"{session_id}.json"
    if session_file.exists():
        with open(session_file, 'r') as f:
            return json.load(f)
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
        for line in iter(process.stdout.readline, b''):
            if line:
                text = line.decode('utf-8', errors='replace').strip()
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
        for line in iter(process.stderr.readline, b''):
            if line:
                text = line.decode('utf-8', errors='replace').rstrip()
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
            error_msg = '\n'.join(stderr_lines[-20:]) if stderr_lines else f"Agent process exited with code {rc}"
            queue.put({"type": "error", "content": error_msg})
        stderr_done_event.set()


def background_worker(session_id, output_queue, process):
    """Read subprocess output and persist to DB, independent of any HTTP connection.
    Runs in a daemon thread. Cleans up session file when subprocess ends."""
    event_counter = 0
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

            if item.get('type') == 'final_answer' and not item.get('agent_name'):
                session_final_answer = (item.get('output') or item.get('content', ''))[:5000]

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
            if status_info and status_info['status'] == 'running':
                complete_session(session_id, final_answer=session_final_answer, status='completed')
        except Exception:
            pass


def cleanup_stale_sessions():
    """On startup, check session files for dead PIDs and mark them as interrupted."""
    try:
        for session_file in SESSION_DIR.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                agent_pid = data.get('agent_pid')
                try:
                    os.kill(agent_pid, 0)  # Check if alive
                except (ProcessLookupError, PermissionError, TypeError):
                    session_id = session_file.stem
                    try:
                        complete_session(session_id, status='interrupted')
                    except Exception:
                        pass
                    session_file.unlink()
            except Exception:
                session_file.unlink(missing_ok=True)
    except Exception as e:
        print(f"Startup cleanup error: {e}")


# Clean up any stale sessions from previous runs
try:
    cleanup_stale_sessions()
except Exception as e:
    print(f"Warning: Failed to clean up stale sessions: {e}")


@app.route("/")
def index():
    """Serve the main HTML page"""
    return render_template("index.html")




@app.route("/api/run/stream", methods=["POST"])
def run_agent_stream():
    """Streaming API endpoint using Server-Sent Events.
    Supports run_mode: 'background' (default), 'auto-kill', 'session-bound'."""
    try:
        data = request.json
        question = data.get("question", "").strip()
        model_id = data.get("model_id", "o1")
        run_mode = data.get("run_mode", "background")

        if run_mode not in ('background', 'auto-kill', 'session-bound'):
            run_mode = 'background'

        if not question:
            return jsonify({"error": "Question is required"}), 400

        # Create session with unique ID
        session_id = str(uuid.uuid4())
        output_queue = Queue()

        # Start agent in subprocess
        env = os.environ.copy()
        process = subprocess.Popen(
            [sys.executable, '-u', 'run.py', question, '--model-id', model_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            bufsize=1
        )

        # Get PIDs
        agent_pid = process.pid
        worker_pid = os.getpid()

        # Write session to shared file (accessible by all workers)
        write_session_file(session_id, agent_pid, worker_pid, run_mode)

        # Store session in this worker's memory
        with sessions_lock:
            active_sessions[session_id] = {
                'process': process,
                'queue': output_queue
            }

        # Shared event so stdout reader waits for stderr to finish
        stderr_done = threading.Event()

        # Start thread to read JSON lines from process stdout
        reader_thread = threading.Thread(
            target=read_process_output,
            args=(process, output_queue, stderr_done),
            daemon=True
        )
        reader_thread.start()

        # Drain stderr and capture errors for the client
        stderr_thread = threading.Thread(
            target=drain_stderr,
            args=(process, output_queue, stderr_done),
            daemon=True
        )
        stderr_thread.start()

        # Persist session to database
        try:
            db_create_session(session_id, question, model_id, run_mode)
        except Exception as db_err:
            print(f"DB: Failed to create session: {db_err}")

        if run_mode in ('background', 'session-bound'):
            # Background/session-bound: decouple subprocess from HTTP connection.
            # Background worker persists events to DB independently.
            # Client connects to /api/sessions/<id>/live for streaming.
            bg_thread = threading.Thread(
                target=background_worker,
                args=(session_id, output_queue, process),
                daemon=True
            )
            bg_thread.start()

            def generate_background():
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"

            return Response(
                stream_with_context(generate_background()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # Auto-kill mode: original coupled behavior.
            # generate() reads subprocess output, persists to DB, and streams SSE.
            # Client disconnect kills the subprocess.
            def generate():
                event_counter = 0
                session_final_answer = None
                interrupted = False

                try:
                    # Send session_id as first message
                    yield f"data: {json.dumps({'session_id': session_id})}\n\n"

                    while True:
                        item = output_queue.get()
                        if item is None:  # End of stream
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break

                        # Persist event to database
                        try:
                            append_event(session_id, event_counter, item)
                            event_counter += 1
                        except Exception as db_err:
                            print(f"DB: Failed to append event: {db_err}")

                        # Track final answer for session summary
                        if item.get('type') == 'final_answer' and not item.get('agent_name'):
                            session_final_answer = (item.get('output') or item.get('content', ''))[:5000]

                        # Item is a structured JSON event from run.py callbacks
                        yield f"data: {json.dumps(item)}\n\n"

                except GeneratorExit:
                    interrupted = True
                    # Client disconnected (closed browser, navigated away, network error)
                    print(f"Client disconnected for session {session_id}, killing agent...")

                    # Kill the agent subprocess
                    with sessions_lock:
                        if session_id in active_sessions:
                            session = active_sessions[session_id]
                            proc = session.get('process')
                            if proc and proc.poll() is None:
                                try:
                                    proc.kill()
                                    proc.wait(timeout=1)
                                except:
                                    pass

                    # Mark session as interrupted in DB
                    try:
                        complete_session(session_id, final_answer=session_final_answer, status='interrupted')
                    except Exception:
                        pass
                    raise  # Re-raise to properly close the generator

                finally:
                    # Always cleanup (whether completed or disconnected)
                    with sessions_lock:
                        if session_id in active_sessions:
                            del active_sessions[session_id]
                    delete_session_file(session_id)

                    # Mark session as completed in DB (skip if already marked as interrupted)
                    if not interrupted:
                        try:
                            complete_session(session_id, final_answer=session_final_answer, status='completed')
                        except Exception:
                            pass

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                }
            )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop/<session_id>", methods=["POST"])
def stop_session(session_id):
    """Stop a running agent session. Mode-aware: auto-kill also kills the worker."""
    try:
        # Read session from shared file (works across workers)
        session_data = read_session_file(session_id)

        if not session_data:
            return jsonify({"success": False, "message": "Session not found"}), 404

        agent_pid = session_data['agent_pid']
        worker_pid = session_data['worker_pid']
        run_mode = session_data.get('run_mode', 'background')

        # Mark session as stopped in DB before killing processes
        try:
            complete_session(session_id, status='stopped')
        except Exception:
            pass

        # Kill the agent subprocess
        try:
            os.kill(agent_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Already dead

        if run_mode == 'auto-kill':
            # Auto-kill mode: also kill the worker to unstick the coupled generate()
            def kill_worker():
                time.sleep(0.5)  # Give time to send response
                try:
                    os.kill(worker_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # Already dead

            threading.Thread(target=kill_worker, daemon=True).start()
        # Background/session-bound: no need to kill worker.
        # The background_worker thread will notice the process died and clean up.

        # Cleanup session file
        delete_session_file(session_id)

        return jsonify({
            "success": True,
            "message": "Agent terminated"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/models", methods=["GET"])
def get_models():
    """Return list of available models"""
    models = [
        {"id": "o1", "name": "OpenAI o1", "description": "Advanced reasoning model"},
        {
            "id": "gpt-4-turbo",
            "name": "GPT-4 Turbo",
            "description": "Fast and powerful",
        },
        {
            "id": "gpt-4.1-mini",
            "name": "GPT-4.1 Mini",
            "description": "Lightweight and efficient",
        },
        {
            "id": "gpt-4.1-nano",
            "name": "GPT-4.1 Nano",
            "description": "Ultra-lightweight model",
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "description": "Efficient and cost-effective",
        },
        {
            "id": "deepseek/deepseek-chat",
            "name": "DeepSeek Chat",
            "description": "Fast chat model from DeepSeek",
        },
        {
            "id": "deepseek/deepseek-reasoner",
            "name": "DeepSeek Reasoner",
            "description": "Reasoning model from DeepSeek",
        },
        {"id": "ollama/mistral", "name": "Ollama Mistral", "description": "Local model"},
        {
            "id": "claude-3-5-sonnet-20241022",
            "name": "Claude 3.5 Sonnet",
            "description": "Anthropic model",
        },
    ]
    return jsonify(models)


# ===== Session History API =====

@app.route("/api/sessions", methods=["GET"])
def api_list_sessions():
    """Return paginated session list for sidebar"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
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
        return jsonify(session)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/live")
def session_live_stream(session_id):
    """SSE stream: replay existing events from DB, then poll for new ones.
    Used for reconnecting to background sessions."""
    after_order = request.args.get('after_order', -1, type=int)

    def generate_live():
        nonlocal after_order

        # Send session_id first
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        # Check session exists
        status_info = get_session_status(session_id)
        if not status_info:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Session not found'})}\n\n"
            return

        # Replay existing events from DB (after the given order)
        existing_events = get_events_after(session_id, after_order)
        for evt_row in existing_events:
            yield f"data: {json.dumps(evt_row['event_data'])}\n\n"
            after_order = evt_row['event_order']

        # If session already finished, send done and return
        if status_info['status'] != 'running':
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        # Poll for new events until session ends
        while True:
            time.sleep(0.5)

            new_events = get_events_after(session_id, after_order)
            for evt_row in new_events:
                yield f"data: {json.dumps(evt_row['event_data'])}\n\n"
                after_order = evt_row['event_order']

            status_info = get_session_status(session_id)
            if not status_info or status_info['status'] != 'running':
                yield f"data: {json.dumps({'done': True})}\n\n"
                break

    return Response(
        stream_with_context(generate_live()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """Delete a session and its events"""
    try:
        deleted = db_delete_session(session_id)
        if not deleted:
            return jsonify({"error": "Session not found"}), 404
        return jsonify({"success": True})
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
