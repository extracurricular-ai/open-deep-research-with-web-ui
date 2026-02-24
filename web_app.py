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

load_dotenv(override=True)

app = Flask(__name__, template_folder="templates")
CORS(app)

# Session tracking directory (shared across all workers)
SESSION_DIR = Path(tempfile.gettempdir()) / "open_deep_research_sessions"
SESSION_DIR.mkdir(exist_ok=True)

# In-memory session tracking for this worker
active_sessions = {}  # session_id -> {'process': subprocess.Popen, 'queue': Queue}
sessions_lock = threading.Lock()


def write_session_file(session_id, agent_pid, worker_pid):
    """Write session info to shared file"""
    session_file = SESSION_DIR / f"{session_id}.json"
    with open(session_file, 'w') as f:
        json.dump({
            'agent_pid': agent_pid,
            'worker_pid': worker_pid,
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
        if process.returncode and process.returncode != 0:
            # Collect meaningful error lines (skip blank lines, tracebacks are useful)
            error_msg = '\n'.join(stderr_lines[-20:]) if stderr_lines else f"Agent process exited with code {process.returncode}"
            queue.put({"type": "error", "content": error_msg})
        stderr_done_event.set()


@app.route("/")
def index():
    """Serve the main HTML page"""
    return render_template("index.html")




@app.route("/api/run/stream", methods=["POST"])
def run_agent_stream():
    """Streaming API endpoint using Server-Sent Events"""
    try:
        data = request.json
        question = data.get("question", "").strip()
        model_id = data.get("model_id", "o1")

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
        write_session_file(session_id, agent_pid, worker_pid)

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

        # Stream responses
        def generate():
            try:
                # Send session_id as first message
                yield f"data: {json.dumps({'session_id': session_id})}\n\n"

                while True:
                    item = output_queue.get()
                    if item is None:  # End of stream
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        break
                    # Item is a structured JSON event from run.py callbacks
                    yield f"data: {json.dumps(item)}\n\n"

            except GeneratorExit:
                # Client disconnected (closed browser, navigated away, network error)
                print(f"⚠️ Client disconnected for session {session_id}, cleaning up...")

                # Kill the agent subprocess
                with sessions_lock:
                    if session_id in active_sessions:
                        session = active_sessions[session_id]
                        process = session.get('process')
                        if process and process.poll() is None:
                            try:
                                process.kill()
                                process.wait(timeout=1)
                            except:
                                pass
                raise  # Re-raise to properly close the generator

            finally:
                # Always cleanup (whether completed or disconnected)
                with sessions_lock:
                    if session_id in active_sessions:
                        del active_sessions[session_id]
                delete_session_file(session_id)

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
    """Stop a running agent session by killing both agent and worker processes"""
    try:
        # Read session from shared file (works across workers)
        session_data = read_session_file(session_id)

        if not session_data:
            return jsonify({"success": False, "message": "Session not found"}), 404

        agent_pid = session_data['agent_pid']
        worker_pid = session_data['worker_pid']

        # Kill the agent subprocess
        try:
            os.kill(agent_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # Already dead

        # Kill the worker process (Gunicorn will restart it)
        def kill_worker():
            time.sleep(0.5)  # Give time to send response
            try:
                os.kill(worker_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass  # Already dead

        threading.Thread(target=kill_worker, daemon=True).start()

        # Cleanup session file
        delete_session_file(session_id)

        return jsonify({
            "success": True,
            "message": "Agent and worker terminated (worker will restart automatically)"
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5080)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--debug", type=bool, default=True)
    args = parser.parse_args()

    print(f"Starting web UI at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
