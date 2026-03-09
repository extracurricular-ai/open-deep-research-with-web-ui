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
- **灵活的模型支持** —— 任何兼容 LiteLLM 的模型（OpenAI、Claude、DeepSeek、Ollama 等）
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

开源的 Deep Research 替代方案有很多，以下是本项目与它们的对比：

| 功能 | **本项目** | [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | [langchain/open_deep_research](https://github.com/langchain-ai/open_deep_research) | [smolagents](https://github.com/huggingface/smolagents) |
|---|---|---|---|---|---|
| **Docker / 一键部署** | ✅ GHCR 预构建镜像 | ✅ Dockerfile | ✅ Docker Compose | ❌ 手动部署 | ❌ 仅库文件 |
| **无需构建前端** | ✅ Preact + htm（无需构建） | ❌ 需要 Next.js 构建 | ❌ 需要 Next.js 构建 | ❌ LangGraph Studio | — |
| **开箱即用免费搜索** | ✅ DuckDuckGo（无需密钥） | ❌ 需要 Firecrawl API | ⚠️ 推荐使用密钥 | ⚠️ 可配置 | ✅ |
| **模型无关** | ✅ 任意 LiteLLM 模型 | ✅ AI SDK 提供商 | ✅ 多种提供商 | ✅ 可配置 | ✅ |
| **本地模型支持** | ✅ Ollama、LM Studio | ⚠️ 有限 | ✅ Ollama/Groq | ✅ | ✅ |
| **并行后台任务** | ✅ 多任务同时运行 | ❌ | ❌ | ❌ | ❌ |
| **会话历史 / 回放** | ✅ SQLite 支持 | ❌ | ❌ | ❌ | ❌ |
| **流式 UI** | ✅ SSE，3 种运行模式 | ✅ 实时活动 | ✅ WebSocket | ✅ 类型安全流 | ❌ |
| **视觉 / 图像分析** | ✅ PDF 截图、视觉问答 | ❌ | ⚠️ 有限 | ❌ | ⚠️ |
| **音频 / YouTube** | ✅ 转录、语音 | ❌ | ❌ | ❌ | ❌ |
| **GAIA 基准分数** | **55% pass@1** | — | — | — | 55%（原始） |

### 本项目的核心优势

- **并行后台研究** —— 本领域最独特的功能。同时启动多个深度研究任务 —— 每个任务作为独立子进程运行，将所有事件持久化到 SQLite，可独立监控或回放。关闭浏览器，数小时后返回，结果依然等待着你。其他开源深度研究工具均不支持此工作流。
- **单条 `docker run` 部署** —— GHCR 预构建镜像可在任何支持 Docker 的平台上运行：Linux、macOS、Windows、ARM、云虚拟机、树莓派。
- **无需构建步骤** —— 前端使用带 `htm` 模板字面量的 Preact。无需 Node.js，无需 `npm install`，无需 webpack。直接打开浏览器。
- **默认免费** —— DuckDuckGo 搜索无需 API 密钥，只需添加一个模型 API 密钥即可立即使用。
- **更广泛的媒体支持** —— 处理其他项目留给用户自行解决的 PDF、图像、音频文件和 YouTube 字幕。

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

配置通过 `odr-config.json`（推荐）或环境变量管理。

### odr-config.json

将 `odr-config.example.json` 复制到 `odr-config.json` 并自定义：

```json
{
  "model": {
    "providers": [
      {
        "name": "openai",
        "api_key": "sk-...",
        "models": ["gpt-4o", "o1", "o3-mini"]
      }
    ],
    "default": "gpt-4o"
  },
  "search": {
    "providers": [
      { "name": "DDGS" },
      { "name": "META_SOTA", "api_key": "your_key" }
    ]
  }
}
```

UI 包含内置设置面板用于客户端配置。服务器端配置可选择使用管理员密码保护。

### 环境变量

对于 Docker 或不方便使用配置文件的环境，可以使用 `.env`：

```bash
cp .env.example .env
```

| 变量 | 描述 |
|---|---|
| `ENABLE_CONFIG_UI` | 通过 Web 启用管理配置 UI（默认 `false`） |
| `CONFIG_ADMIN_PASSWORD` | 服务器端配置更改密码 |
| `META_SOTA_API_KEY` | MetaSo 搜索的 API 密钥 |
| `SERPAPI_API_KEY` | SerpAPI 搜索的 API 密钥 |
| `DEBUG` | 启用调试日志（默认 `False`） |
| `LOG_LEVEL` | 日志详细程度（默认 `INFO`） |

> [!NOTE]
> 在 `odr-config.json` 中设置的 API 密钥优先于环境变量。

### 支持的模型

任何 [LiteLLM 兼容](https://docs.litellm.ai/docs/providers)的模型均可使用。示例：

```bash
python run.py --model-id "gpt-4o" "你的问题"
python run.py --model-id "o1" "你的问题"
python run.py --model-id "claude-sonnet-4-6" "你的问题"
python run.py --model-id "deepseek/deepseek-chat" "你的问题"
python run.py --model-id "ollama/mistral" "你的问题"  # 本地模型
```

> [!WARNING]
> `o1` 模型需要 OpenAI tier-3 API 访问权限：https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini

### 搜索引擎

| 引擎 | 需要密钥 | 备注 |
|---|---|---|
| `DDGS` | 否 | 默认，免费 DuckDuckGo |
| `META_SOTA` | 是 | MetaSo，对中文查询效果更好 |
| `SERPAPI` | 是 | 通过 SerpAPI 使用 Google |

可配置多个引擎并自动降级 —— 智能体按顺序尝试。

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
