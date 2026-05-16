# Open Deep Research

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io-blue)](https://ghcr.io/s2thend/open-deep-research-with-ui)

> **Read this in other languages:** 🇨🇳 [中文](docs/README_zh.md) · 🇫🇷 [Français](docs/README_fr.md) · 🇪🇸 [Español](docs/README_es.md)

An open replication of [OpenAI's Deep Research](https://openai.com/index/introducing-deep-research/) with a modern web UI — adapted from [HuggingFace smolagents](https://github.com/huggingface/smolagents/tree/main/examples) with simplified configuration for easy self-hosting.

Read more about the original implementation in the [HuggingFace blog post](https://huggingface.co/blog/open-deep-research).

This agent achieves **55% pass@1** on the GAIA validation set, compared to **67%** for OpenAI's Deep Research.

---

## Features

- **Parallel background research** — fire off multiple research tasks simultaneously, monitor them independently, and come back to results later — even after closing the browser
- **Multi-agent research pipeline** — Manager + search sub-agents with real-time streaming output
- **Modern Web UI** — Preact-based SPA with collapsible sections, model selector, and copy support
- **Flexible model support** — OpenAI, Anthropic, DeepSeek, Ollama, and any OpenAI-compatible provider
- **Multiple search engines** — DuckDuckGo (free), SerpAPI, MetaSo with automatic fallback
- **Session history** — SQLite-backed session storage with replay support
- **Three run modes** — Live (real-time), Background (persistent), Auto-kill (one-shot)
- **Model auto-discovery** — Detects available models from configured providers
- **Vision & media tools** — Image QA, PDF analysis, audio transcription, YouTube transcripts
- **Production-ready** — Docker, Gunicorn, multi-worker, health checks, configurable via JSON

**Screenshots:**

<div align="center">
  <img src="docs/imgs/ui_input.png" alt="Web UI Input" width="800"/>
  <p><em>Clean input interface with model selection</em></p>

  <img src="docs/imgs/ui_tools_plans.png" alt="Agent Plans and Tools" width="800"/>
  <p><em>Real-time display of agent reasoning, tool calls, and observations</em></p>

  <img src="docs/imgs/ui_result.png" alt="Final Results" width="800"/>
  <p><em>Highlighted final answer with collapsible sections</em></p>
</div>

---

## Parallel Background Research

Deep research tasks are slow — a single run can take 10–30 minutes. Most tools block the UI until the task completes, forcing you to wait.

This project takes a different approach: **fire off as many research tasks as you want and let them run in the background — simultaneously.**

```
┌─────────────────────────────────────────────────────┐
│  Question A: "What are the latest advances in LLMs?" │  ← running
│  Question B: "Compare top vector databases in 2025"  │  ← running
│  Question C: "EU AI Act compliance checklist"        │  ← completed ✓
└─────────────────────────────────────────────────────┘
        All visible in the sidebar. Click any to inspect.
```

**How it works:**

1. Select **Background** or **Auto-kill** run mode (the default)
2. Submit your first research question — the agent starts immediately in a subprocess
3. The UI is not locked — submit a second question, a third, as many as you need
4. Each agent runs independently, persisting all its reasoning steps and results to SQLite
5. Use the sidebar to switch between running sessions in real-time
6. Close the browser — in **Background** mode, agents keep running on the server
7. Return later and click any session to replay the full research trace

**Run mode comparison:**

| Mode | Multiple at once | Survives browser close | UI locked |
|---|---|---|---|
| **Background** | ✅ | ✅ | ✗ |
| **Auto-kill** | ✅ | ✗ (killed on tab close) | ✗ |
| **Live** | ✗ | ✗ | ✅ |

This is particularly useful for:
- Batch research workflows where you queue several related questions and review results together
- Long-running queries where you don't want to keep a tab open
- Teams sharing a self-hosted instance with multiple concurrent users

---

## Why This Project?

- **One-command Docker install, zero config to start** — `docker run -p 5080:5080 ghcr.io/s2thend/open-deep-research-with-ui:latest` and a working web UI is up. DuckDuckGo search is built-in; one model API key is enough to begin.

- **No LiteLLM dependency** — direct OpenAI + Anthropic SDK calls only. Removes the intermediary translation layer that LiteLLM has had repeated security advisories for. Safer for enterprise / internal deployments.

- **Air-gap-friendly, self-hostable** — no telemetry, no external service dependencies beyond the model + search APIs you explicitly configure. Pair with Ollama / LM Studio / vLLM for fully offline operation behind any firewall.

- **Built to be forked** — ~3K LOC Python on top of smolagents. Add a tool by dropping a file in `scripts/`; swap providers via `scripts/model_routing.py`; hook into agent step callbacks (see `scripts/compaction.py`). A starting point for *your* internal research agent, not a closed product.

- **Multi-provider search with auto-fallback** — DDGS, Tavily, SerpAPI, MetaSo, Bocha — wired up out of the box. Configure as an ordered list; the agent walks the chain on empty results or rate-limit errors. Cross-regional, China-hosted, and air-gapped friendly.

- **Parallel background research** — the most unique feature in this space. Run multiple research tasks simultaneously; each persists to SQLite. Close the browser, return hours later, results are waiting. No other open-source deep research tool supports this.

### Comparison with alternatives

| Feature | **This project** | [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | [langchain/open_deep_research](https://github.com/langchain-ai/open_deep_research) | [smolagents](https://github.com/huggingface/smolagents) |
|---|---|---|---|---|---|
| **Docker / one-command deploy** | ✅ Pre-built image on GHCR | ✅ Dockerfile | ✅ Docker Compose | ❌ Manual | ❌ Library only |
| **No LiteLLM dependency** | ✅ Direct OpenAI + Anthropic SDKs | ⚠️ AI SDK layer | ⚠️ | ⚠️ langchain layer | ✅ |
| **Air-gapped / internal deploy** | ✅ No telemetry, no external deps | ⚠️ Depends on Firecrawl | ⚠️ Cloud-leaning defaults | ⚠️ LangGraph Studio | ✅ |
| **Multi-provider search w/ fallback** | ✅ DDGS + Tavily + SerpAPI + MetaSo + Bocha | ❌ Firecrawl only | ⚠️ Single per run | ⚠️ Configurable | ⚠️ DIY |
| **Regional model providers** | ✅ DeepSeek first-class | ⚠️ US-centric | ⚠️ US-centric | ⚠️ US-centric | ✅ |
| **No-build frontend** | ✅ Preact + htm (no build step) | ❌ Next.js build required | ❌ Next.js build required | ❌ LangGraph Studio | — |
| **Free search out of the box** | ✅ DuckDuckGo (no key needed) | ❌ Firecrawl API required | ⚠️ Key recommended | ⚠️ Configurable | ✅ |
| **Local model support** | ✅ Ollama, LM Studio | ⚠️ Limited | ✅ Ollama/Groq | ✅ | ✅ |
| **Parallel background tasks** | ✅ Multiple simultaneous runs | ❌ | ❌ | ❌ | ❌ |
| **Session history / replay** | ✅ SQLite-backed | ❌ | ❌ | ❌ | ❌ |
| **Streaming UI** | ✅ SSE, 3 run modes | ✅ Real-time activity | ✅ WebSocket | ✅ Type-safe stream | ❌ |
| **Vision / image analysis** | ✅ PDF screenshots, visual QA | ❌ | ⚠️ Limited | ❌ | ⚠️ |
| **Audio / YouTube** | ✅ Transcription, speech | ❌ | ❌ | ❌ | ❌ |
| **GAIA benchmark score** | **55% pass@1** | — | — | — | 55% (original) |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/S2thend/open-deep-research-with-ui.git
cd open-deep-research-with-ui
```

### 2. Install system dependencies

The project requires **FFmpeg** for audio processing.

- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`
- **Windows**: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html)

Verify: `ffmpeg -version`

### 3. Install Python dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

### 4. Configure

Copy the example config and add your API keys:

```bash
cp odr-config.example.json odr-config.json
```

Edit `odr-config.json` to set your model provider and API keys (see [Configuration](#configuration) below).

### 5. Run

```bash
# Web UI (recommended)
python web_app.py
# Open http://localhost:5080

# CLI
python run.py --model-id "gpt-4o" "Your research question here"
```

---

## Configuration

Two layers of configuration:

1. **`odr-config.json`** — primary, JSON, controls everything (models, agent behavior, search providers, browser, limits, compaction). Auto-created from `odr-config.example.json` on first run.
2. **`.env`** — optional, for secrets you'd rather keep out of JSON or for Docker deployments.

API keys in `odr-config.json` take precedence over `.env` values when both are set.

### odr-config.json reference

Copy `odr-config.example.json` to `odr-config.json` and edit. The full schema:

```json
{
  "agent": {
    "search_agent_max_steps": 20,
    "manager_agent_max_steps": 12,
    "planning_interval": 4,
    "verbosity_level": 2
  },
  "model": {
    "providers": [
      {"provider": "openai",    "api_key": "sk-...", "base_url": ""},
      {"provider": "deepseek",  "api_key": "",       "base_url": ""},
      {"provider": "anthropic", "api_key": "",       "base_url": ""}
    ],
    "default_model_id": "o1",
    "max_completion_tokens": 32768,
    "reasoning_effort": "high",
    "retry_max_attempts": 5,
    "retry_wait_seconds": 30
  },
  "search": {
    "providers": [
      {"provider": "DDGS",      "key": ""},
      {"provider": "TAVILY",    "key": ""},
      {"provider": "SERPAPI",   "key": ""},
      {"provider": "META_SOTA", "key": ""},
      {"provider": "BOCHA",     "key": ""}
    ],
    "max_results": 10
  },
  "browser": {
    "viewport_size": 5120,
    "request_timeout": 300
  },
  "limits": {
    "text_limit": 100000,
    "max_field_length": 50000
  },
  "compaction": {
    "enabled": true,
    "summarizer_model_id": null,
    "summary_threshold_tokens": 1000,
    "summary_max_tokens": 600,
    "summary_input_cap_tokens": 6000,
    "plan_keep_back": 3,
    "gap_summary_max_tokens": 500,
    "max_retries": 10
  },
  "other_keys": {"hf_token": ""},
  "models": [ /* UI dropdown — list of {id, name, description} */ ]
}
```

The UI exposes a settings panel that edits the same file. Server-side edits via the UI are gated behind `CONFIG_ADMIN_PASSWORD` if `ENABLE_CONFIG_UI=true`.

#### `agent` — multi-step research loop

| Key | Default | Effect |
|---|---|---|
| `search_agent_max_steps` | `20` | Max ReAct steps the **search sub-agent** takes per task. Each step is one LLM call + one tool call (web search, browse, text inspect). Bigger = deeper research per sub-task, but each extra step accumulates ~5–30K tokens of observation in context. |
| `manager_agent_max_steps` | `12` | Max steps the **manager** takes. Each step usually delegates to a sub-agent or synthesizes results. Rarely needs raising; if you hit the cap, the question is probably better split. |
| `planning_interval` | `4` | Insert a "re-plan" step every N action steps. Lower = more course-correction (better when the agent loses focus); higher = fewer planning calls (cheaper, faster). |
| `verbosity_level` | `2` | Logger verbosity. `0` silent, `1` info, `2` debug. |

#### `model` — LLM provider routing

| Key | Default | Effect |
|---|---|---|
| `providers[]` | OpenAI/DeepSeek/Anthropic stubs | List of credentials. Each entry: `{"provider": "<openai\|deepseek\|anthropic\|...>", "api_key": "...", "base_url": ""}`. The `base_url` field lets you point at a self-hosted or proxy endpoint that speaks the provider's wire format (e.g. Ollama's OpenAI-compatible API). The first provider matching the chosen `default_model_id`'s routing is used. |
| `default_model_id` | `"o1"` | Which model the agent uses. Routing is automatic based on the prefix — see [Supported Models](#supported-models). Override per-run with `--model-id`. |
| `max_completion_tokens` | `32768` | Output token cap **before clamping**. Each model has a hard ceiling (gpt-4o-mini: 16K, deepseek-chat: 8K, o1: 100K, claude-sonnet-4: 64K). The effective value passed to the API is `min(this_setting, model_cap)` — if you keep the default `32768`, smaller models silently clamp to their own ceiling so you never get a 4xx for "max_tokens too large". Lowering only helps if you want shorter outputs; raising past the model cap is a no-op. |
| `reasoning_effort` | `"high"` | Only used when `default_model_id` is `"o1"`. Values: `"low"`, `"medium"`, `"high"`. Trade-off between latency/cost and reasoning depth. |
| `retry_max_attempts` | `5` | How many times to retry transient errors (HTTP 429, connection drops, partial reads). Note: this does **not** retry on context-overflow / 400-class errors, which are unrecoverable. |
| `retry_wait_seconds` | `30` | Initial backoff between retries. Doubles each attempt with jitter (exponential backoff). |

#### `search` — search providers and result count

| Key | Default | Effect |
|---|---|---|
| `providers[]` | DDGS first, others empty | Ordered fallback chain. The agent tries the first provider; if it returns no results or errors, it moves to the next. Add a `key` field per entry (DDGS doesn't need one). See [Search Engines](#search-engines) below for the full provider list. |
| `max_results` | `10` | How many search results returned per query. Each result is a title + snippet + URL (~few hundred tokens). Bigger = wider net, but more tokens in observation. Lower if you're hitting context limits and not using compaction. |

#### `browser` — text browser tool

| Key | Default | Effect |
|---|---|---|
| `viewport_size` | `5120` | Characters visible per page-view in the simulated browser. The agent uses `page_up`/`page_down` to scroll. Larger = fewer scroll calls but bigger observations. Smaller = more navigation steps but each observation is smaller. |
| `request_timeout` | `300` | Seconds to wait for an HTTP fetch before giving up. Slow sites or tiny VMs may need higher. |

#### `limits` — content size guards

| Key | Default | Effect |
|---|---|---|
| `text_limit` | `100000` | Max characters returned by `text_inspector_tool` (the file-reader for PDFs / large docs). Keeps a single `inspect_file_as_text` call from blowing up the agent's memory. |
| `max_field_length` | `50000` | Max characters per **SSE event field** sent to the frontend (display-side only — does **not** reduce LLM input). Lowering this just saves bandwidth between server and browser. |

#### `compaction` — LLM-based context compaction (Layer 1 + Layer 2)

Without this, smolagents accumulates every step's raw observation forever and 20-step research runs reliably blow past model context windows. See `scripts/compaction.py` for the implementation.

| Key | Default | Effect |
|---|---|---|
| `enabled` | `true` | Master switch. Set `false` to fall back to raw-observation behavior (faster per step, but long runs may crash on context overflow). |
| `summarizer_model_id` | `null` | `null` = use the agent's main model (simplest, no extra config). Override with a cheap model id (e.g. `"deepseek-chat"`) to lower cost/latency of summarization. **Currently the override path is reserved for a future PR; today the value is read but the main model is always used.** |
| `summary_threshold_tokens` | `1000` | **Layer 1**: skip per-step summarization if the observation is shorter than this (in tokens, counted via tiktoken `cl100k_base`). Below 1000 tokens, the savings don't outweigh the LLM call cost. |
| `summary_max_tokens` | `600` | **Layer 1**: target output length of the per-step summary. The summary preserves facts, numbers, and URLs; drops navigation chrome and repetitive HTML. |
| `summary_input_cap_tokens` | `6000` | **Layer 1**: max input fed to the summarizer (head + tail trim if observation is bigger). Caps the summarizer's own context cost. |
| `plan_keep_back` | `3` | **Layer 2**: how many recent plan-gaps stay uncompacted. With `planning_interval=4` and 20 search-agent steps, this fires once during a typical run (compacting the oldest gap). Lower (`2` or `1`) to consolidate more aggressively. |
| `gap_summary_max_tokens` | `500` | **Layer 2**: target length of each consolidated gap summary. URLs from the gap are appended verbatim. |
| `max_retries` | `10` | Retries for the compaction LLM call (own retry layer on top of the model's internal retrier). Mirrors Claude Code's default budget. After exhaustion, falls back to head+tail token truncation rather than crashing the run. |

#### `other_keys` — miscellaneous tokens

| Key | Default | Effect |
|---|---|---|
| `hf_token` | `""` | HuggingFace token. Only required when running the GAIA benchmark (`run_gaia.py`) which downloads the validation dataset. |

#### `models` — UI dropdown

A pure-display list of `{id, name, description}` triples for the model picker in the web UI. Editing this only affects the UI. The actual model used is whatever `default_model_id` (or CLI `--model-id`) resolves to.

### Environment variables

For Docker or when you'd rather not put secrets in JSON, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Effect |
|---|---|
| `ENABLE_CONFIG_UI` | If `true`, exposes the server-side config editing endpoint in the UI. Defaults to `false`. |
| `CONFIG_ADMIN_PASSWORD` | Password gate for the server-side config UI. Required when `ENABLE_CONFIG_UI=true`. |
| `META_SOTA_API_KEY` | API key for MetaSo search. Used as fallback when `search.providers[].key` is empty. |
| `SERPAPI_API_KEY` | API key for SerpAPI search. Same fallback rule. |
| `BOCHA_API_KEY` | API key for Bocha AI (博查) search. Same fallback rule. |
| `TAVILY_API_KEY` | API key for Tavily search. Same fallback rule. |
| `OPENAI_API_KEY` | OpenAI key. Used when `model.providers[]` openai entry has no `api_key`. |
| `ANTHROPIC_API_KEY` | Anthropic key. Same fallback rule. |
| `DEEPSEEK_API_KEY` | DeepSeek key. Same fallback rule. |
| `HF_TOKEN` | HuggingFace token. Same fallback for `other_keys.hf_token`. |
| `DEBUG` | Enable debug logging (`false` by default). |
| `LOG_LEVEL` | Log verbosity — `DEBUG`, `INFO`, `WARNING`, `ERROR` (`INFO` by default). |

> [!NOTE]
> Keys set in `odr-config.json` take precedence over `.env` values.

### Supported Models

Supports OpenAI, Anthropic, DeepSeek, Ollama, and any OpenAI-compatible provider. Model routing is automatic from the model id prefix. Examples:

```bash
python run.py --model-id "gpt-4o" "Your question"
python run.py --model-id "o1" "Your question"
python run.py --model-id "claude-sonnet-4-6" "Your question"
python run.py --model-id "deepseek/deepseek-chat" "Your question"
python run.py --model-id "ollama/mistral" "Your question"  # local model
```

`max_completion_tokens` is automatically clamped to each model's published output ceiling (see `scripts/model_routing.py` for the full table). You don't need to lower the config when switching to a small-cap model.

> [!WARNING]
> The `o1` model requires OpenAI tier-3 API access: https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini

### Search Engines

| Engine | Key Required | Notes |
|---|---|---|
| `DDGS` | No | DuckDuckGo, free, default. |
| `TAVILY` | Yes | Tavily, often the best result quality for English queries. |
| `META_SOTA` | Yes | MetaSo, optimized for Chinese queries. |
| `SERPAPI` | Yes | Google results via SerpAPI. |
| `BOCHA` | Yes | Bocha AI (博查), Chinese-optimized web search. |

Multiple engines can be listed in `search.providers[]` — the agent tries them in order and falls through to the next on empty results or errors.

---

## Usage

### Web UI

```bash
python web_app.py
# or with custom host/port:
python web_app.py --port 8000 --host 0.0.0.0
```

Open `http://localhost:5080` in your browser.

**Run modes** (available via the split-button in the UI):

| Mode | Behavior |
|---|---|
| **Live** | Stream output in real-time; session ends on disconnect |
| **Background** | Agent runs persistently; reconnect anytime to view results |
| **Auto-kill** | Agent runs, session is cleaned up after completion |

### CLI

```bash
python run.py --model-id "gpt-4o" "What are the latest advances in quantum computing?"
```

### GAIA Benchmark

```bash
# Requires HF_TOKEN for dataset download
python run_gaia.py --model-id "o1" --run-name my-run
```

---

## Deployment

### Docker (Recommended)

**Pre-built images** are available on GitHub Container Registry:

```bash
docker pull ghcr.io/s2thend/open-deep-research-with-ui:latest

docker run -d \
  --env-file .env \
  -v ./odr-config.json:/app/odr-config.json \
  -p 5080:5080 \
  --name open-deep-research \
  ghcr.io/s2thend/open-deep-research-with-ui:latest
```

**Docker Compose** (includes volume for downloaded files):

```bash
cp .env.example .env        # configure API keys
cp odr-config.example.json odr-config.json  # configure models
docker-compose up -d
docker-compose logs -f      # follow logs
docker-compose down         # stop
```

**Build your own image:**

```bash
docker build -t open-deep-research .
docker run -d --env-file .env -p 5080:5080 open-deep-research
```

> [!WARNING]
> Never commit `.env` or `odr-config.json` with real API keys to git. Always pass secrets at runtime.

### Gunicorn (Production)

```bash
pip install -e .
gunicorn -c gunicorn.conf.py web_app:app
```

The included `gunicorn.conf.py` is pre-configured with:
- Multi-worker process management
- 300s timeout for long-running agent tasks
- Proper logging and error handling

---

## Architecture

### Agent Pipeline

```
User Question
    │
    ▼
Manager Agent (CodeAgent / ToolCallingAgent)
    │  Plans multi-step research strategy
    ├──▶ Search Sub-Agent × N
    │       │  Web search → browse → extract
    │       └──▶ Tools: DuckDuckGo/SerpAPI/MetaSo, VisitWebpage,
    │                   TextInspector, VisualQA, YoutubeTranscript
    │
    └──▶ Final Answer synthesis
```

### Streaming Pipeline

```
run.py  (step_callbacks → JSON-lines on stdout)
  │
  ▼
web_app.py  (subprocess → Server-Sent Events)
  │
  ▼
Browser  (Preact components → DOM)
```

**SSE event types:**

| Event | Description |
|---|---|
| `planning_step` | Agent reasoning and plan |
| `code_running` | Code being executed |
| `action_step` | Tool call + observation |
| `final_answer` | Completed research result |
| `error` | Error with details |

### DOM Hierarchy

```
#output
├── step-container.plan-step       (manager plan)
├── step-container                 (manager step)
│   └── step-children
│       ├── model-output           (reasoning)
│       ├── Agent Call             (code, collapsed)
│       └── sub-agent-container
│           ├── step-container.plan-step  (sub-agent plan)
│           ├── step-container            (sub-agent steps)
│           └── sub-agent-result          (preview + collapsible)
└── final_answer                   (prominent result block)
```

---

## Reproducibility (GAIA Results)

The 55% pass@1 result on GAIA was obtained with augmented data:

- Single-page PDFs and XLS files were opened and screenshotted as `.png`
- The file loader checks for a `.png` version of each attachment and prefers it

The augmented dataset is available at [smolagents/GAIA-annotated](https://huggingface.co/datasets/smolagents/GAIA-annotated) (access granted instantly on request).

---

## Development

```bash
pip install -e ".[dev]"   # includes testing, linting, type checking tools
python web_app.py         # starts dev server with auto-reload
```

The frontend is a dependency-free Preact app using `htm` for JSX-like templates — no build step required. Edit files in `static/js/components/` and refresh.

---

## License

Licensed under the **Apache License 2.0** — the same license as [smolagents](https://github.com/huggingface/smolagents).

See [LICENSE](LICENSE) for details.

**Acknowledgments:**
- Original research agent implementation by [HuggingFace smolagents](https://github.com/huggingface/smolagents)
- Web UI, session management, streaming architecture, and configuration system added in this fork
