import argparse
import io
import os
import sys
import threading
from contextlib import redirect_stdout
from queue import Queue

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, stream_with_context, Response
from flask_cors import CORS

from run import create_agent
from output_formatter import OutputFormatter

load_dotenv(override=True)

app = Flask(__name__, template_folder="templates")
CORS(app)

# Queue for streaming output
output_queue = None
output_lock = threading.Lock()


class StreamingOutputCapture:
    """Captures stdout, formats it, and queues for streaming to frontend"""

    def __init__(self, queue):
        self.queue = queue
        self.original_stdout = sys.stdout
        self.formatter = OutputFormatter()

    def write(self, text):
        # Format the output
        output = self.formatter.add_text(text)
        if output:
            self.queue.put(output)

        # Also print to console
        self.original_stdout.write(text)
        sys.stdout.flush()

    def flush(self):
        # Flush any remaining content
        output = self.formatter.flush()
        if output:
            self.queue.put(output)


@app.route("/")
def index():
    """Serve the main HTML page"""
    return render_template("index.html")


def run_agent_thread(question, model_id, queue):
    """Run the agent in a separate thread and stream output"""
    old_stdout = sys.stdout
    sys.stdout = StreamingOutputCapture(queue)

    try:
        # Create and run agent
        print(f"Using model: {model_id}")
        print(f"Question: {question}")
        print("-" * 80)

        agent = create_agent(model_id=model_id)
        answer = agent.run(question)

        print("-" * 80)
        print(f"✓ Final Answer: {answer}")
        queue.put(None)  # Signal end of stream

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        queue.put(None)  # Signal end of stream
    finally:
        sys.stdout = old_stdout


@app.route("/api/run/stream", methods=["POST"])
def run_agent_stream():
    """Streaming API endpoint using Server-Sent Events"""
    global output_queue

    try:
        data = request.json
        question = data.get("question", "").strip()
        model_id = data.get("model_id", "o1")

        if not question:
            return jsonify({"error": "Question is required"}), 400

        # Create a new queue for this run
        output_queue = Queue()

        # Start agent in background thread
        agent_thread = threading.Thread(
            target=run_agent_thread,
            args=(question, model_id, output_queue),
            daemon=True
        )
        agent_thread.start()

        # Stream responses
        import json
        def generate():
            while True:
                item = output_queue.get()
                if item is None:  # End of stream
                    yield f"data: {json.dumps({'done': True})}\n\n"
                    break
                # Item is already a structured dict from the formatter
                yield f"data: {json.dumps(item)}\n\n"

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
            "id": "deepseek-chat",
            "name": "DeepSeek Chat",
            "description": "Fast chat model from DeepSeek",
        },
        {
            "id": "deepseek-reasoner",
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
