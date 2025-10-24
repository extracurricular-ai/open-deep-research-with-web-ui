import argparse
import os
import threading
import requests
import json

from dotenv import load_dotenv
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
            print(f"📡 Using DuckDuckGo search engine")
            tools.append(DuckDuckGoSearchToolLabeled(max_results=max_results))
        elif engine == "META_SOTA":
            api_key = os.getenv("META_SOTA_API_KEY")
            if not api_key:
                print(f"⚠️  META_SOTA_API_KEY not found, skipping MetaSo search")
                continue
            print(f"📡 Using MetaSo search engine")
            tools.append(MetaSotaSearchTool(api_key=api_key, max_results=max_results))
        else:
            print(f"⚠️  Unknown search engine: {engine}, skipping")

    if not tools:
        print(f"⚠️  No valid search engines configured, falling back to DuckDuckGo")
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
    )

    return manager_agent


def main():
    args = parse_args()

    agent = create_agent(model_id=args.model_id)

    answer = agent.run(args.question)

    print(f"✓ Final Answer: {answer}")


if __name__ == "__main__":
    main()
