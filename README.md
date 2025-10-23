# Open Deep Research

Welcome to this open replication of [OpenAI's Deep Research](https://openai.com/index/introducing-deep-research/)! This agent attempts to replicate OpenAI's model and achieve similar performance on research tasks.

Read more about this implementation's goal and methods in our [blog post](https://huggingface.co/blog/open-deep-research).


This agent achieves **55% pass@1** on the GAIA validation set, compared to **67%** for the original Deep Research.

## Setup

To get started, follow the steps below:

### Clone the repository

```bash
git clone https://github.com/huggingface/smolagents.git
cd smolagents/examples/open_deep_research
```

### Install system dependencies

The project uses `pydub` and `SpeechRecognition` which require **FFmpeg** for audio processing and format conversion.

**Install FFmpeg:**

- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`
- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or `choco install ffmpeg`

Verify installation: `ffmpeg -version`

### Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

For development tools (testing, linting, type checking):

```bash
pip install -e ".[dev]"
```

### Set up environment variables

Create a `.env` file from the `.env.example` template and configure the following variables:

**Required:**
- `OPENAI_API_KEY` - For the visual QA tool (image analysis) and if using OpenAI models
  - [Sign up here to get a key](https://platform.openai.com/signup)

**Optional:**
- `HF_TOKEN` - Only required for `run_gaia.py` (for downloading datasets)
  - [Get your token here](https://huggingface.co/settings/tokens)

**Web search:**
The project uses `DuckDuckGoSearchTool` by default (no API key required). If you want to use alternative search providers, you can modify the tool configuration in `run.py`.

**Model selection:**
Depending on the model you want to use, set the corresponding environment variables:
- For `o1` model (default): `OPENAI_API_KEY` required
- For other OpenAI-compatible models: Follow the provider's documentation
- For local models (Ollama, LM Studio): No API key required

> [!WARNING]
> The use of the default `o1` model is restricted to tier-3 access: https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini


## Usage

Make sure your virtual environment is activated and environment variables are set.

### Command Line Interface

```bash
python run.py --model-id "o1" "Your question here!"
```

Or use other models via LiteLLM:

```bash
python run.py --model-id "ollama/mistral" "Your question here!"
python run.py --model-id "claude-3-5-sonnet-20241022" "Your question here!"
```

### Web UI (Recommended)

Start the web server:

```bash
python web_app.py
```

Then open your browser to `http://localhost:5080`

The web UI provides:
- 🎨 Modern, responsive interface
- 📝 Question input form
- 🤖 Model selection dropdown
- 📊 Real-time output display
- ✨ Highlighted final answers

You can also customize the server:

```bash
python web_app.py --port 8000 --host 0.0.0.0
```

### GAIA Benchmark Evaluation

For the GAIA benchmark evaluation:

```bash
python run_gaia.py --model-id "o1" --run-name my-run
```

## Full reproducibility of results

The data used in our submissions to GAIA was augmented in this way:
 -  For each single-page .pdf or .xls file, it was opened in a file reader (MacOS Sonoma Numbers or Preview), and a ".png" screenshot was taken and added to the folder.
- Then for any file used in a question, the file loading system checks if there is a ".png" extension version of the file, and loads it instead of the original if it exists.

This process was done manually but could be automatized.

After processing, the annotated was uploaded to a [new dataset](https://huggingface.co/datasets/smolagents/GAIA-annotated). You need to request access (granted instantly).