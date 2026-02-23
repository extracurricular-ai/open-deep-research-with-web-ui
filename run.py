import argparse
import datetime
import os
import sys
import threading
import requests
import json

from dotenv import load_dotenv
from rich.console import Console
from smolagents.monitoring import AgentLogger
from smolagents.memory import ActionStep, PlanningStep, FinalAnswerStep

from scripts.text_inspector_tool import TextInspectorTool
from scripts.text_web_browser import (
    ArchiveSearchTool,
    FinderTool,
    FindNextTool,
    PageDownTool,
    PageUpTool,
    SimpleTextBrowser,
    VisitTool,
)
from scripts.visual_qa import visualizer

from smolagents import (
    CodeAgent,
    DuckDuckGoSearchTool,
    LiteLLMModel,
    Tool,
    ToolCallingAgent,
)


# --- JSON protocol for structured output ---
# Save real stdout for JSON events, redirect sys.stdout to stderr
# so any print() from libraries/tools goes to stderr, keeping stdout
# exclusively for our structured JSON lines.
_json_out = sys.stdout
sys.stdout = sys.stderr

_emit_lock = threading.Lock()
MAX_FIELD_LENGTH = 50000


def _truncate(s, max_len=MAX_FIELD_LENGTH):
    """Truncate large strings to avoid huge JSON lines."""
    if s and isinstance(s, str) and len(s) > max_len:
        return s[:max_len] + f"\n... [truncated, {len(s)} total chars]"
    return s


def emit_event(event_type, **data):
    """Emit a JSON-lines event to the real stdout."""
    try:
        event = {"type": event_type, **data}
        line = json.dumps(event, default=str)
        with _emit_lock:
            _json_out.write(line + "\n")
            _json_out.flush()
    except Exception as e:
        sys.stderr.write(f"emit_event error: {e}\n")


def _extract_model_reasoning(step):
    """Extract LLM reasoning text from model_output, excluding code blocks.

    model_output can be:
      - str: plain reasoning text
      - list[dict]: content blocks like [{"type":"text","text":"..."}]
      - None: model produced only tool calls with no text

    For CodeAgent: model_output includes the code block which is already
    in code_action, so we strip it out to get just the reasoning.
    """
    import re

    raw = step.model_output
    if raw is None:
        return None

    # Handle list of content blocks (e.g. [{"type":"text","text":"..."}])
    if isinstance(raw, list):
        parts = []
        for block in raw:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text", "").strip()
                if t:
                    parts.append(t)
        text = "\n".join(parts)
    elif isinstance(raw, str):
        text = raw.strip()
    else:
        return None

    if not text:
        return None

    # If there's a code_action, the model_output contains it embedded in
    # code block tags. Strip the code block to get just the reasoning.
    if step.code_action:
        # Remove fenced code blocks (```...```)
        text = re.sub(r'```[\s\S]*?```', '', text).strip()
        # Remove smolagents code block tags (<code>...</code> variants)
        text = re.sub(r'<[^>]*code[^>]*>[\s\S]*?</[^>]*code[^>]*>', '', text, flags=re.IGNORECASE).strip()

    # Strip raw tool-call JSON that leaks into model_output when the agent
    # is interrupted mid-generation (e.g. "Calling tools:\n[{...}]")
    text = re.sub(r'Calling tools:\s*\[[\s\S]*', '', text).strip()

    return text if text else None


def on_action_step(step, agent=None):
    """Callback for ActionStep — emits structured step data."""
    agent_name = getattr(agent, 'name', None) if agent else None

    tool_calls_data = []
    if step.tool_calls:
        for tc in step.tool_calls:
            tool_calls_data.append({
                "name": tc.name,
                "arguments": tc.arguments,
            })

    model_reasoning = _extract_model_reasoning(step)

    # Debug: log model_output type and presence to stderr
    import sys
    raw_mo = step.model_output
    print(f"[debug] step={step.step_number} agent={agent_name} model_output type={type(raw_mo).__name__} "
          f"len={len(raw_mo) if raw_mo else 0} reasoning={'yes' if model_reasoning else 'no'}",
          file=sys.stderr)

    emit_event(
        "action_step",
        step_number=step.step_number,
        agent_name=agent_name,
        model_output=_truncate(model_reasoning) if model_reasoning else None,
        tool_calls=tool_calls_data,
        code_action=step.code_action,
        observations=_truncate(step.observations),
        error=str(step.error) if step.error else None,
        is_final_answer=step.is_final_answer,
        action_output=_truncate(str(step.action_output)) if step.action_output is not None else None,
        duration=step.timing.duration,
        token_usage=step.token_usage.dict() if step.token_usage else None,
    )


def on_planning_step(step, agent=None):
    """Callback for PlanningStep — emits plan text."""
    agent_name = getattr(agent, 'name', None) if agent else None
    emit_event(
        "planning_step",
        plan=step.plan,
        agent_name=agent_name,
        duration=step.timing.duration,
        token_usage=step.token_usage.dict() if step.token_usage else None,
    )


def on_final_answer(step, agent=None):
    """Callback for FinalAnswerStep — emits final answer."""
    agent_name = getattr(agent, 'name', None) if agent else None
    emit_event(
        "final_answer",
        output=str(step.output),
        agent_name=agent_name,
    )


_step_callbacks = {
    ActionStep: on_action_step,
    PlanningStep: on_planning_step,
    FinalAnswerStep: on_final_answer,
}

class StreamingLogger(AgentLogger):
    """Custom logger that emits lightweight JSON events for real-time UI feedback.

    Only emits code_running (from log_code) which fires right before the
    CodeAgent executes generated code. This fills the UI gap between the LLM
    response and the step_callback result.

    We intentionally do NOT emit events from log_rule or log_task because:
    - log_rule fires for every agent's step but carries no agent_name, so the
      renderer can't place it in the correct nesting context (causes duplicate
      step containers at wrong levels).
    - log_task fires when sub-agents launch, but step_callbacks already carry
      agent_name which drives sub-agent nesting correctly.
    """

    def __init__(self):
        _devnull = open(os.devnull, "w")
        super().__init__(level=0, console=Console(file=_devnull, highlight=False))

    def log_code(self, title, content, level=0):
        """Fired when code is about to be executed."""
        emit_event("code_running", title=title, code=_truncate(content, 2000))


_streaming_logger = StreamingLogger()


load_dotenv(override=True)


class DuckDuckGoSearchToolLabeled(DuckDuckGoSearchTool):
    """Wrapper around DuckDuckGoSearchTool to add engine label to results"""

    def forward(self, query: str) -> str:
        result = super().forward(query)
        # Replace "## Search Results" with "## Search Results (DuckDuckGo)"
        return result.replace("## Search Results\n\n", "## Search Results (DuckDuckGo)\n\n", 1)


class MetaSotaSearchTool(Tool):
    name = "web_search"
    description = "Search the web using MetaSo search engine. Returns search results with title, link, and snippet."
    inputs = {
        "query": {
            "type": "string",
            "description": "The search query to look up on the web",
        }
    }
    output_type = "string"

    def __init__(self, api_key: str, max_results: int = 10, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.max_results = max_results
        self.api_url = "https://metaso.cn/api/v1/search"

    def forward(self, query: str) -> str:
        """Search the web using MetaSo API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "q": query,
            "scope": "webpage",
            "includeSummary": False,
            "size": str(self.max_results),
            "includeRawContent": False,
            "conciseSnippet": False,
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Format results similar to DuckDuckGo output
            # MetaSo returns results in 'webpages' array
            webpages = data.get("webpages", [])
            if not webpages:
                return "No results found."

            results = []
            for item in webpages[:self.max_results]:
                title = item.get("title", "No title")
                link = item.get("link", "")  # MetaSo uses 'link' not 'url'
                snippet = item.get("snippet", "No description")
                results.append(f"|{title}]({link})\n{snippet}\n")

            return "## Search Results (MetaSo)\n\n" + "\n".join(results)

        except requests.exceptions.RequestException as e:
            return f"Error performing search: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

append_answer_lock = threading.Lock()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "question", type=str, help="for example: 'How many studio albums did Mercedes Sosa release before 2007?'"
    )
    parser.add_argument("--model-id", type=str, default="o1")
    return parser.parse_args()


custom_role_conversions = {"tool-call": "assistant", "tool-response": "user"}

user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"

BROWSER_CONFIG = {
    "viewport_size": 1024 * 5,
    "downloads_folder": "downloads_folder",
    "request_kwargs": {
        "headers": {"User-Agent": user_agent},
        "timeout": 300,
    },
    "serpapi_key": os.getenv("SERPAPI_API_KEY"),
}

os.makedirs(f"./{BROWSER_CONFIG['downloads_folder']}", exist_ok=True)


def get_search_tools(max_results=10):
    """Get search tools based on SEARCH_ENGINE environment variable.

    Returns a list of search tools with fallback support.
    SEARCH_ENGINE can be: DDGS, META_SOTA, or comma-separated for fallback (e.g., META_SOTA,DDGS)
    """
    search_engine = os.getenv("SEARCH_ENGINE", "DDGS")
    engines = [e.strip() for e in search_engine.split(",")]

    tools = []
    for engine in engines:
        if engine == "DDGS":
            emit_event("info", content="Using DuckDuckGo search engine")
            tools.append(DuckDuckGoSearchToolLabeled(max_results=max_results))
        elif engine == "META_SOTA":
            api_key = os.getenv("META_SOTA_API_KEY")
            if not api_key:
                emit_event("info", content="META_SOTA_API_KEY not found, skipping MetaSo search")
                continue
            emit_event("info", content="Using MetaSo search engine")
            tools.append(MetaSotaSearchTool(api_key=api_key, max_results=max_results))
        else:
            emit_event("info", content=f"Unknown search engine: {engine}, skipping")

    if not tools:
        emit_event("info", content="No valid search engines configured, falling back to DuckDuckGo")
        tools.append(DuckDuckGoSearchToolLabeled(max_results=max_results))

    return tools


def create_agent(model_id="o1"):
    model_params = {
        "model_id": model_id,
        "custom_role_conversions": custom_role_conversions,
        "max_completion_tokens": 8192,
    }
    if model_id == "o1":
        model_params["reasoning_effort"] = "high"
    model = LiteLLMModel(**model_params)

    text_limit = 100000
    browser = SimpleTextBrowser(**BROWSER_CONFIG)

    # Get search tools based on environment configuration
    search_tools = get_search_tools(max_results=10)

    WEB_TOOLS = [
        *search_tools,  # Add configured search engine(s)
        VisitTool(browser),
        PageUpTool(browser),
        PageDownTool(browser),
        FinderTool(browser),
        FindNextTool(browser),
        ArchiveSearchTool(browser),
        TextInspectorTool(model, text_limit),
    ]
    text_webbrowser_agent = ToolCallingAgent(
        model=model,
        tools=WEB_TOOLS,
        max_steps=20,
        verbosity_level=2,
        planning_interval=4,
        name="search_agent",
        description="""A team member that will search the internet to answer your question.
    Ask him for all your questions that require browsing the web.
    Provide him as much context as possible, in particular if you need to search on a specific timeframe!
    And don't hesitate to provide him with a complex search task, like finding a difference between two webpages.
    Your request must be a real sentence, not a google search! Like "Find me this information (...)" rather than a few keywords.
    """,
        provide_run_summary=True,
        step_callbacks=_step_callbacks,
        logger=_streaming_logger,
    )
    text_webbrowser_agent.prompt_templates["managed_agent"]["task"] += """You can navigate to .txt online files.
    If a non-html page is in another format, especially .pdf or a Youtube video, use tool 'inspect_file_as_text' to inspect it.
    Additionally, if after some searching you find out that you need more information to answer the question, you can use `final_answer` with your request for clarification as argument to request for more information."""

    # Restrict imports for security - only allow pure data processing modules
    # Block file I/O: os, subprocess, shutil, pathlib, io, open
    # Block network: requests, urllib, http, socket
    # Block image/file libs: PIL, cv2, imageio
    safe_imports = [
        "math", "re", "json", "datetime", "time",
        "collections", "itertools", "functools", "typing",
        "statistics", "random", "string", "decimal"
    ]

    manager_agent = CodeAgent(
        model=model,
        tools=[visualizer, TextInspectorTool(model, text_limit)],
        max_steps=12,
        verbosity_level=2,
        additional_authorized_imports=safe_imports,
        planning_interval=4,
        managed_agents=[text_webbrowser_agent],
        step_callbacks=_step_callbacks,
        logger=_streaming_logger,
    )
    # Inject custom instructions into the system prompt template.
    # This nudges the CodeAgent to use Python execution for things it can
    # compute directly (dates, math, parsing) instead of delegating everything.
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    manager_agent.prompt_templates["system_prompt"] = (
        manager_agent.prompt_templates["system_prompt"].rstrip()
        + "\n\n"
        + f"Current date and time: {now}\n\n"
        + "You can execute Python code directly — use this whenever it is more "
        "efficient than delegating to search_agent. For example: use datetime "
        "to get the current date/time, use math/statistics for calculations, "
        "use json/re to parse or transform data, and use string operations to "
        "process text. Prepare as much context as possible in code (dates, "
        "computed values, formatted queries) before delegating web searches to "
        "search_agent, and pass that context in the task description. "
        "When providing the final answer, include all important details, "
        "findings, and sources from the search results. Do not over-summarize "
        "or omit key information gathered by search_agent."
    )

    return manager_agent


def main():
    args = parse_args()

    agent = create_agent(model_id=args.model_id)

    agent.run(args.question)


if __name__ == "__main__":
    main()
