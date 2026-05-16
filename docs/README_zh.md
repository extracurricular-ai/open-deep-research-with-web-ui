# Open Deep Research

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io-blue)](https://ghcr.io/s2thend/open-deep-research-with-ui)

[OpenAI Deep Research](https://openai.com/index/introducing-deep-research/) 的开源复现，配备现代化 Web UI —— 基于 [HuggingFace smolagents](https://github.com/huggingface/smolagents/tree/main/examples) 改编，配置简化，易于自部署。

原始实现详见 [HuggingFace 博客文章](https://huggingface.co/blog/open-deep-research)。

本智能体在 GAIA 验证集上达到 **55% pass@1**，对比 OpenAI Deep Research 的 **67%**。

---

## 功能特性

- **并行后台研究** —— 同时发起多个研究任务，独立监控，随时查看结果 —— 即使关闭浏览器也不影响
- **多智能体研究流水线** —— 管理者 + 搜索子智能体，实时流式输出
- **现代化 Web UI** —— 基于 Preact 的单页应用，支持折叠面板、模型选择器和复制功能
- **灵活的模型支持** —— OpenAI、Anthropic、DeepSeek、Ollama 及任何 OpenAI 兼容的提供商
- **多搜索引擎** —— DuckDuckGo（免费）、SerpAPI、MetaSo，支持自动降级
- **会话历史** —— 基于 SQLite 的会话存储，支持回放
- **三种运行模式** —— 实时（Live）、后台（Background）、自动终止（Auto-kill）
- **模型自动发现** —— 自动检测已配置提供商的可用模型
- **视觉与媒体工具** —— 图像问答、PDF 分析、音频转录、YouTube 字幕
- **生产就绪** —— Docker、Gunicorn、多工作进程、健康检查、JSON 配置

**截图：**

<div align="center">
  <img src="imgs/ui_input.png" alt="Web UI 输入界面" width="800"/>
  <p><em>简洁的输入界面，支持模型选择</em></p>

  <img src="imgs/ui_tools_plans.png" alt="智能体计划与工具" width="800"/>
  <p><em>实时展示智能体推理过程、工具调用和观察结果</em></p>

  <img src="imgs/ui_result.png" alt="最终结果" width="800"/>
  <p><em>高亮显示的最终答案，支持折叠展开</em></p>
</div>

---

## 并行后台研究

深度研究任务耗时较长 —— 单次运行可能需要 10–30 分钟。大多数工具会在任务完成前锁定 UI，迫使你等待。

本项目采用不同的方式：**同时发起任意数量的研究任务，让它们在后台并行运行。**

```
┌─────────────────────────────────────────────────────┐
│  问题 A："大语言模型的最新进展是什么？"              │  ← 运行中
│  问题 B："对比 2025 年顶级向量数据库"               │  ← 运行中
│  问题 C："欧盟 AI 法案合规清单"                     │  ← 已完成 ✓
└─────────────────────────────────────────────────────┘
        所有任务都在侧边栏可见，点击任意任务查看详情。
```

**工作原理：**

1. 选择 **Background** 或 **Auto-kill** 运行模式（默认）
2. 提交第一个研究问题 —— 智能体立即在子进程中启动
3. UI 不会被锁定 —— 可继续提交第二个、第三个问题，数量不限
4. 每个智能体独立运行，将所有推理步骤和结果持久化到 SQLite
5. 使用侧边栏实时切换各运行会话
6. 关闭浏览器 —— 在 **Background** 模式下，智能体继续在服务器上运行
7. 稍后返回，点击任意会话即可回放完整的研究轨迹

**运行模式对比：**

| 模式 | 多任务并行 | 浏览器关闭后继续 | UI 锁定 |
|---|---|---|---|
| **Background** | ✅ | ✅ | ✗ |
| **Auto-kill** | ✅ | ✗（标签页关闭后终止） | ✗ |
| **Live** | ✗ | ✗ | ✅ |

特别适用于：
- 批量研究工作流，将多个相关问题排队并统一查看结果
- 长时间运行的查询，无需保持标签页开启
- 多用户共享自部署实例的团队

---

## 为什么选择本项目？

- **一行 Docker 命令即装即用，无需配置** —— `docker run -p 5080:5080 ghcr.io/s2thend/open-deep-research-with-ui:latest` 启动后立即可用。DuckDuckGo 搜索内置，只需一个模型 API 密钥即可开始研究。

- **不依赖 LiteLLM** —— 仅直接调用 OpenAI + Anthropic 官方 SDK。移除了 LiteLLM 这个反复出现安全公告的中间翻译层。对企业 / 内网部署更安全。

- **支持气隙环境、可自托管** —— 无遥测、无任何托管服务依赖，仅与你显式配置的模型和搜索 API 通信。配合 Ollama / LM Studio / vLLM 可完全离线运行在任何防火墙之内。

- **为 fork 而生** —— smolagents 之上约 3K 行 Python。新增工具只需往 `scripts/` 丢一个文件；切换 provider 改 `scripts/model_routing.py`；钩进 agent step callbacks（见 `scripts/compaction.py`）。是*你自己*内部研究 agent 的起点，不是封闭产品。

- **多搜索 provider 自动降级** —— 开箱即用接入 DDGS、Tavily、SerpAPI、MetaSo、博查。配置为有序列表后，agent 会在结果为空或撞 rate-limit 时自动顺降。跨区域、中国托管、气隙环境全部友好。

- **并行后台研究** —— 本领域最独特的功能。同时运行多个研究任务，每个都持久化到 SQLite。关闭浏览器，数小时后回来，结果还在。其他开源深度研究工具均不支持此工作流。

### 与其他方案对比

| 功能 | **本项目** | [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | [langchain/open_deep_research](https://github.com/langchain-ai/open_deep_research) | [smolagents](https://github.com/huggingface/smolagents) |
|---|---|---|---|---|---|
| **Docker / 一键部署** | ✅ GHCR 预构建镜像 | ✅ Dockerfile | ✅ Docker Compose | ❌ 手动部署 | ❌ 仅库文件 |
| **不依赖 LiteLLM** | ✅ 直接 OpenAI + Anthropic SDK | ⚠️ AI SDK 层 | ⚠️ | ⚠️ langchain 层 | ✅ |
| **气隙 / 内网部署** | ✅ 无遥测、无外部依赖 | ⚠️ 依赖 Firecrawl | ⚠️ 默认走云 | ⚠️ LangGraph Studio | ✅ |
| **多 provider 搜索带降级** | ✅ DDGS + Tavily + SerpAPI + MetaSo + 博查 | ❌ 仅 Firecrawl | ⚠️ 单次单 provider | ⚠️ 可配置 | ⚠️ DIY |
| **区域性模型 provider** | ✅ DeepSeek 一等支持 | ⚠️ 偏美国 | ⚠️ 偏美国 | ⚠️ 偏美国 | ✅ |
| **无需构建前端** | ✅ Preact + htm（无需构建） | ❌ 需要 Next.js 构建 | ❌ 需要 Next.js 构建 | ❌ LangGraph Studio | — |
| **开箱即用免费搜索** | ✅ DuckDuckGo（无需密钥） | ❌ 需要 Firecrawl API | ⚠️ 推荐使用密钥 | ⚠️ 可配置 | ✅ |
| **本地模型支持** | ✅ Ollama、LM Studio | ⚠️ 有限 | ✅ Ollama/Groq | ✅ | ✅ |
| **并行后台任务** | ✅ 多任务同时运行 | ❌ | ❌ | ❌ | ❌ |
| **会话历史 / 回放** | ✅ SQLite 支持 | ❌ | ❌ | ❌ | ❌ |
| **流式 UI** | ✅ SSE，3 种运行模式 | ✅ 实时活动 | ✅ WebSocket | ✅ 类型安全流 | ❌ |
| **视觉 / 图像分析** | ✅ PDF 截图、视觉问答 | ❌ | ⚠️ 有限 | ❌ | ⚠️ |
| **音频 / YouTube** | ✅ 转录、语音 | ❌ | ❌ | ❌ | ❌ |
| **GAIA 基准分数** | **55% pass@1** | — | — | — | 55%（原始） |

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/S2thend/open-deep-research-with-ui.git
cd open-deep-research-with-ui
```

### 2. 安装系统依赖

项目需要 **FFmpeg** 进行音频处理。

- **macOS**：`brew install ffmpeg`
- **Linux**：`sudo apt-get install ffmpeg`
- **Windows**：`choco install ffmpeg` 或从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载

验证：`ffmpeg -version`

### 3. 安装 Python 依赖

```bash
python3 -m venv venv
source venv/bin/activate  # Windows 上：venv\Scripts\activate
pip install -e .
```

### 4. 配置

复制示例配置并添加你的 API 密钥：

```bash
cp odr-config.example.json odr-config.json
```

编辑 `odr-config.json` 设置模型提供商和 API 密钥（见下方[配置](#配置)部分）。

### 5. 运行

```bash
# Web UI（推荐）
python web_app.py
# 打开 http://localhost:5080

# CLI
python run.py --model-id "gpt-4o" "你的研究问题"
```

---

## 配置

两层配置：

1. **`odr-config.json`** —— 主配置，JSON 格式，控制一切（模型、智能体行为、搜索提供商、浏览器、限制、压缩）。首次运行时从 `odr-config.example.json` 自动创建。
2. **`.env`** —— 可选，用于不想放在 JSON 中的密钥，或 Docker 部署。

两边都设置时，`odr-config.json` 中的 API 密钥优先。

### odr-config.json 全字段参考

将 `odr-config.example.json` 复制为 `odr-config.json` 后编辑。完整 schema：

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
  "models": [ /* UI 下拉框 —— {id, name, description} 列表 */ ]
}
```

UI 自带设置面板编辑同一份文件。当 `ENABLE_CONFIG_UI=true` 时，服务器端编辑接口由 `CONFIG_ADMIN_PASSWORD` 保护。

#### `agent` —— 多步研究循环

| 字段 | 默认 | 作用 |
|---|---|---|
| `search_agent_max_steps` | `20` | **search 子智能体**单次任务最多走多少步 ReAct。每步 = 一次 LLM 调用 + 一次工具调用（搜索/浏览/读文档）。越大越深，但每多一步累加 5–30K tokens 的 observation 进上下文。 |
| `manager_agent_max_steps` | `12` | **manager** 最多走几步。每步通常委托给子智能体或综合结果。一般不需要调高；撞顶通常意味着问题该拆。 |
| `planning_interval` | `4` | 每 N 个 action step 插入一次"重新规划"。低 = 更频繁纠偏（适合智能体跑偏的场景）；高 = 减少 planning 调用（更便宜更快）。 |
| `verbosity_level` | `2` | 日志详细程度。`0` 静默，`1` info，`2` debug。 |

#### `model` —— LLM 提供商路由

| 字段 | 默认 | 作用 |
|---|---|---|
| `providers[]` | OpenAI/DeepSeek/Anthropic 占位 | 凭据列表。每项：`{"provider": "<openai\|deepseek\|anthropic\|...>", "api_key": "...", "base_url": ""}`。`base_url` 用于指向自托管或代理端点（兼容该 provider 的 wire 协议，例如 Ollama 的 OpenAI 兼容 API）。`default_model_id` 路由到的第一个匹配 provider 被使用。 |
| `default_model_id` | `"o1"` | 智能体使用的模型。按前缀自动路由 —— 见[支持的模型](#支持的模型)。每次运行可用 `--model-id` 覆盖。 |
| `max_completion_tokens` | `32768` | 输出 token 上限**未 clamp 前**的值。每个模型都有硬上限（gpt-4o-mini: 16K，deepseek-chat: 8K，o1: 100K，claude-sonnet-4: 64K）。实际传给 API 的是 `min(此设置, 模型上限)` —— 保留默认 `32768`，小模型会自动 clamp 到自己的上限，永远不会因为 "max_tokens too large" 报 4xx。调小只在你想限制输出长度时有用；调高超过模型上限是 no-op。 |
| `reasoning_effort` | `"high"` | 仅当 `default_model_id` 为 `"o1"` 时生效。可选 `"low"`、`"medium"`、`"high"`。在延迟/成本和推理深度间权衡。 |
| `retry_max_attempts` | `5` | 临时错误（HTTP 429、连接掉、partial read）重试次数。注意：**不**对 context 超限 / 400 类错误重试（这些不可恢复）。 |
| `retry_wait_seconds` | `30` | 重试初始 backoff，每次翻倍 + jitter（指数退避）。 |

#### `search` —— 搜索提供商和结果数

| 字段 | 默认 | 作用 |
|---|---|---|
| `providers[]` | DDGS 排首位，其余空 | 有序降级链。智能体先用第一个；返回空或报错则换下一个。每项加 `key` 字段（DDGS 不需要）。完整 provider 列表见下方[搜索引擎](#搜索引擎)。 |
| `max_results` | `10` | 每次搜索返回多少条结果。每条 = title + snippet + URL（几百 tokens）。大 = 网撒得宽，但 observation 更长。如果撞 context 上限且没开 compaction，可以调低。 |

#### `browser` —— 文本浏览器工具

| 字段 | 默认 | 作用 |
|---|---|---|
| `viewport_size` | `5120` | 模拟浏览器单次显示的字符数。智能体用 `page_up`/`page_down` 翻页。大 = 翻页少但 observation 大；小 = 多次翻页但每次小。 |
| `request_timeout` | `300` | HTTP 请求超时秒数。慢站点或小 VM 上可能要调高。 |

#### `limits` —— 内容大小限制

| 字段 | 默认 | 作用 |
|---|---|---|
| `text_limit` | `100000` | `text_inspector_tool`（PDF / 大文档读取器）单次返回的字符上限。防止单个 `inspect_file_as_text` 调用爆掉智能体的 memory。 |
| `max_field_length` | `50000` | 发给前端的**单个 SSE event 字段**字符上限（仅显示侧 —— **不**减少 LLM input）。调低只省 server 到 browser 的带宽。 |

#### `compaction` —— LLM 上下文压缩（Layer 1 + Layer 2）

不开它，smolagents 会无限累积每步的原始 observation，20 步研究任务必撞模型 context 上限。实现见 `scripts/compaction.py`。

| 字段 | 默认 | 作用 |
|---|---|---|
| `enabled` | `true` | 总开关。`false` 退回原始 observation 行为（每步更快，但长任务可能因 context 超限崩溃）。 |
| `summarizer_model_id` | `null` | `null` = 用主模型（最简单，零额外配置）。可以填便宜模型 id（例如 `"deepseek-chat"`）降低摘要成本/延迟。**目前覆盖路径预留给后续 PR；当前读取该值但始终用主模型。** |
| `summary_threshold_tokens` | `1000` | **Layer 1**：observation 短于此 token 数（用 tiktoken `cl100k_base` 计数）则不摘要。低于 1000 tokens 时，摘要省的不抵 LLM 调用本身。 |
| `summary_max_tokens` | `600` | **Layer 1**：每步摘要的目标输出长度。摘要保留事实/数字/URL，丢掉导航 chrome 和重复 HTML。 |
| `summary_input_cap_tokens` | `6000` | **Layer 1**：喂给摘要器的最大 input（observation 超此值则 head + tail 截断）。控制摘要器自己的上下文成本。 |
| `plan_keep_back` | `3` | **Layer 2**：保留最近多少个 plan-gap 不压缩。`planning_interval=4` + 20 步 search-agent 时，典型一次任务触发 1 次（压最老 gap）。降到 `2` 或 `1` 更激进。 |
| `gap_summary_max_tokens` | `500` | **Layer 2**：每段合并 gap summary 的目标长度。该 gap 的 URL 原样附上。 |
| `max_retries` | `10` | 压缩 LLM 调用的重试次数（叠在模型自身重试器上的额外一层）。对齐 Claude Code 默认预算。耗尽后降级到 head+tail token 截断，不让整个 run 崩。 |

#### `other_keys` —— 杂项 token

| 字段 | 默认 | 作用 |
|---|---|---|
| `hf_token` | `""` | HuggingFace token。仅运行 GAIA 基准（`run_gaia.py`）下载验证集时需要。 |

#### `models` —— UI 下拉框

纯展示用的 `{id, name, description}` 列表，给 web UI 模型选择器用。改这里只影响 UI。实际使用的模型由 `default_model_id`（或 CLI `--model-id`）决定。

### 环境变量

Docker 部署或者不愿把密钥放进 JSON 时，把 `.env.example` 复制成 `.env`：

```bash
cp .env.example .env
```

| 变量 | 作用 |
|---|---|
| `ENABLE_CONFIG_UI` | `true` 时在 UI 暴露服务器端配置编辑端点。默认 `false`。 |
| `CONFIG_ADMIN_PASSWORD` | 服务器端配置 UI 的密码。`ENABLE_CONFIG_UI=true` 时必填。 |
| `META_SOTA_API_KEY` | MetaSo 搜索的 API 密钥。`search.providers[].key` 为空时作为 fallback。 |
| `SERPAPI_API_KEY` | SerpAPI 的 API 密钥。同 fallback 规则。 |
| `BOCHA_API_KEY` | 博查 AI（Bocha）搜索的 API 密钥。同 fallback 规则。 |
| `TAVILY_API_KEY` | Tavily 搜索的 API 密钥。同 fallback 规则。 |
| `OPENAI_API_KEY` | OpenAI key。`model.providers[]` openai 项 `api_key` 为空时使用。 |
| `ANTHROPIC_API_KEY` | Anthropic key。同 fallback 规则。 |
| `DEEPSEEK_API_KEY` | DeepSeek key。同 fallback 规则。 |
| `HF_TOKEN` | HuggingFace token。`other_keys.hf_token` 的 fallback。 |
| `DEBUG` | 启用调试日志（默认 `false`）。 |
| `LOG_LEVEL` | 日志详细程度 —— `DEBUG`、`INFO`、`WARNING`、`ERROR`（默认 `INFO`）。 |

> [!NOTE]
> `odr-config.json` 中的密钥优先于 `.env`。

### 支持的模型

支持 OpenAI、Anthropic、DeepSeek、Ollama 及任何 OpenAI 兼容的提供商。模型路由按 model id 前缀自动判断。示例：

```bash
python run.py --model-id "gpt-4o" "你的问题"
python run.py --model-id "o1" "你的问题"
python run.py --model-id "claude-sonnet-4-6" "你的问题"
python run.py --model-id "deepseek/deepseek-chat" "你的问题"
python run.py --model-id "ollama/mistral" "你的问题"  # 本地模型
```

`max_completion_tokens` 自动 clamp 到每个模型公布的输出上限（完整表见 `scripts/model_routing.py`）。切换到小 cap 模型时不需要手动改配置。

> [!WARNING]
> `o1` 模型需要 OpenAI tier-3 API 访问权限：https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini

### 搜索引擎

| 引擎 | 需要密钥 | 备注 |
|---|---|---|
| `DDGS` | 否 | DuckDuckGo，免费，默认。 |
| `TAVILY` | 是 | Tavily，英文查询结果质量通常最好。 |
| `META_SOTA` | 是 | MetaSo，针对中文查询优化。 |
| `SERPAPI` | 是 | 通过 SerpAPI 使用 Google。 |
| `BOCHA` | 是 | 博查 AI（Bocha），针对中文优化的网页搜索。 |

可在 `search.providers[]` 中列多个 —— 智能体按顺序尝试，遇到空结果或报错则降级到下一个。

---

## 使用方法

### Web UI

```bash
python web_app.py
# 或自定义主机/端口：
python web_app.py --port 8000 --host 0.0.0.0
```

在浏览器中打开 `http://localhost:5080`。

**运行模式**（通过 UI 中的分割按钮选择）：

| 模式 | 行为 |
|---|---|
| **Live** | 实时流式输出；断开连接后会话结束 |
| **Background** | 智能体持久运行；随时重连查看结果 |
| **Auto-kill** | 智能体运行，完成后清理会话 |

### CLI

```bash
python run.py --model-id "gpt-4o" "量子计算的最新进展是什么？"
```

### GAIA 基准测试

```bash
# 需要 HF_TOKEN 下载数据集
python run_gaia.py --model-id "o1" --run-name my-run
```

---

## 部署

### Docker（推荐）

**预构建镜像**可在 GitHub Container Registry 获取：

```bash
docker pull ghcr.io/s2thend/open-deep-research-with-ui:latest

docker run -d \
  --env-file .env \
  -v ./odr-config.json:/app/odr-config.json \
  -p 5080:5080 \
  --name open-deep-research \
  ghcr.io/s2thend/open-deep-research-with-ui:latest
```

**Docker Compose**（包含下载文件的挂载卷）：

```bash
cp .env.example .env        # 配置 API 密钥
cp odr-config.example.json odr-config.json  # 配置模型
docker-compose up -d
docker-compose logs -f      # 查看日志
docker-compose down         # 停止
```

**自行构建镜像：**

```bash
docker build -t open-deep-research .
docker run -d --env-file .env -p 5080:5080 open-deep-research
```

> [!WARNING]
> 切勿将含有真实 API 密钥的 `.env` 或 `odr-config.json` 提交到 git。始终在运行时传递密钥。

### Gunicorn（生产环境）

```bash
pip install -e .
gunicorn -c gunicorn.conf.py web_app:app
```

内置的 `gunicorn.conf.py` 已预配置：
- 多工作进程管理
- 长时间运行任务的 300 秒超时
- 适当的日志和错误处理

---

## 架构

### 智能体流水线

```
用户问题
    │
    ▼
管理者智能体（CodeAgent / ToolCallingAgent）
    │  规划多步研究策略
    ├──▶ 搜索子智能体 × N
    │       │  网络搜索 → 浏览 → 提取
    │       └──▶ 工具：DuckDuckGo/SerpAPI/MetaSo、VisitWebpage、
    │                   TextInspector、VisualQA、YoutubeTranscript
    │
    └──▶ 最终答案综合
```

### 流式传输流水线

```
run.py（step_callbacks → stdout 上的 JSON 行）
  │
  ▼
web_app.py（子进程 → 服务器发送事件）
  │
  ▼
浏览器（Preact 组件 → DOM）
```

**SSE 事件类型：**

| 事件 | 描述 |
|---|---|
| `planning_step` | 智能体推理和计划 |
| `code_running` | 正在执行的代码 |
| `action_step` | 工具调用 + 观察结果 |
| `final_answer` | 已完成的研究结果 |
| `error` | 包含详情的错误 |

### DOM 层次结构

```
#output
├── step-container.plan-step       （管理者计划）
├── step-container                 （管理者步骤）
│   └── step-children
│       ├── model-output           （推理）
│       ├── Agent Call             （代码，已折叠）
│       └── sub-agent-container
│           ├── step-container.plan-step  （子智能体计划）
│           ├── step-container            （子智能体步骤）
│           └── sub-agent-result          （预览 + 可折叠）
└── final_answer                   （突出显示的结果块）
```

---

## 可复现性（GAIA 结果）

GAIA 上 55% pass@1 的结果通过增强数据获得：

- 单页 PDF 和 XLS 文件被打开并截图为 `.png`
- 文件加载器检查每个附件的 `.png` 版本并优先使用

增强数据集可在 [smolagents/GAIA-annotated](https://huggingface.co/datasets/smolagents/GAIA-annotated) 获取（申请后即时授权）。

---

## 开发

```bash
pip install -e ".[dev]"   # 包含测试、代码检查、类型检查工具
python web_app.py         # 启动带自动重载的开发服务器
```

前端是使用 `htm` 模板字面量的无依赖 Preact 应用 —— 无需构建步骤。编辑 `static/js/components/` 中的文件并刷新。

---

## 许可证

基于 **Apache License 2.0** 授权 —— 与 [smolagents](https://github.com/huggingface/smolagents) 使用相同的许可证。

详见 [LICENSE](../LICENSE)。

**致谢：**
- 原始研究智能体实现来自 [HuggingFace smolagents](https://github.com/huggingface/smolagents)
- Web UI、会话管理、流式架构和配置系统在本 fork 中添加
