import argparse
import io
import os
import sys
import threading
from contextlib import redirect_stdout

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from run import create_agent

load_dotenv(override=True)

app = Flask(__name__, template_folder="templates")
CORS(app)

# Store for output capture
output_buffer = None
output_lock = threading.Lock()


class OutputCapture:
    """Captures stdout and stores it for frontend display"""

    def __init__(self):
        self.buffer = io.StringIO()
        self.original_stdout = sys.stdout

    def write(self, text):
        self.buffer.write(text)
        self.original_stdout.write(text)  # Also print to console
        sys.stdout.flush()

    def flush(self):
        pass

    def get_output(self):
        return self.buffer.getvalue()

    def reset(self):
        self.buffer = io.StringIO()


@app.route("/")
def index():
    """Serve the main HTML page"""
    return render_template("index.html")


@app.route("/api/run", methods=["POST"])
def run_agent():
    """API endpoint to run the agent with user question"""
    global output_buffer

    try:
        data = request.json
        question = data.get("question", "").strip()
        model_id = data.get("model_id", "o1")

        if not question:
            return jsonify({"error": "Question is required"}), 400

        # Capture output
        output_buffer = OutputCapture()
        old_stdout = sys.stdout

        try:
            sys.stdout = output_buffer

            # Create and run agent
            print(f"Using model: {model_id}")
            print(f"Question: {question}")
            print("-" * 80)

            agent = create_agent(model_id=model_id)
            answer = agent.run(question)

            print("-" * 80)
            print(f"Final Answer: {answer}")

            # Get all captured output
            output_text = output_buffer.get_output()

            return jsonify({"success": True, "answer": answer, "output": output_text}), 200

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(error_msg, file=old_stdout)
            output_text = output_buffer.get_output() if output_buffer else ""
            return (
                jsonify(
                    {
                        "success": False,
                        "error": str(e),
                        "output": output_text,
                    }
                ),
                500,
            )
        finally:
            sys.stdout = old_stdout

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "description": "Efficient and cost-effective",
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
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--debug", type=bool, default=True)
    args = parser.parse_args()

    print(f"Starting web UI at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
