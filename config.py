"""Centralized configuration for Open Deep Research.

Loads settings from odr-config.json with fallback to defaults.
Auto-creates odr-config.json from odr-config.example.json on first run.
"""

import json
import copy
import shutil
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
CONFIG_PATH = CONFIG_DIR / "odr-config.json"
EXAMPLE_PATH = CONFIG_DIR / "odr-config.example.json"

DEFAULTS = {
    "agent": {
        "search_agent_max_steps": 20,
        "manager_agent_max_steps": 12,
        "planning_interval": 4,
        "verbosity_level": 2,
    },
    "model": {
        "providers": [
            {"provider": "openai", "api_key": "", "base_url": ""},
            {"provider": "deepseek", "api_key": "", "base_url": ""},
        ],
        "default_model_id": "o1",
        "max_completion_tokens": 8192,
        "reasoning_effort": "high",
    },
    "search": {
        # Order matters: first provider is primary, rest are tried as fallbacks in list order.
        "providers": [
            {"provider": "DDGS", "key": ""},
            {"provider": "SERPAPI", "key": ""},
            {"provider": "META_SOTA", "key": ""},
        ],
        "max_results": 10,
    },
    "browser": {
        "viewport_size": 5120,
        "request_timeout": 300,
    },
    "limits": {
        "text_limit": 100000,
        "max_field_length": 50000,
    },
    "other_keys": {
        "hf_token": "",
    },
    "models": [
        {"id": "o1", "name": "OpenAI o1", "description": "Advanced reasoning model"},
        {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "description": "Fast and powerful"},
        {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "description": "Lightweight and efficient"},
        {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "description": "Ultra-lightweight model"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "description": "Efficient and cost-effective"},
        {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "description": "Fast chat model from DeepSeek"},
        {"id": "deepseek/deepseek-reasoner", "name": "DeepSeek Reasoner", "description": "Reasoning model from DeepSeek"},
        {"id": "ollama/mistral", "name": "Ollama Mistral", "description": "Local model"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "description": "Anthropic model"},
    ],
}


def _deep_merge(base, override):
    """Deep merge override into base. Returns a new dict.
    Lists are replaced entirely (not merged element-wise)."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config():
    """Load config from odr-config.json, deep-merged with defaults.
    Auto-creates odr-config.json from example if it doesn't exist."""
    if not CONFIG_PATH.exists():
        if EXAMPLE_PATH.exists():
            shutil.copy2(EXAMPLE_PATH, CONFIG_PATH)
        else:
            save_config(DEFAULTS)

    try:
        with open(CONFIG_PATH, "r") as f:
            user_config = json.load(f)
    except (json.JSONDecodeError, OSError):
        user_config = {}

    return _deep_merge(DEFAULTS, user_config)


def save_config(data):
    """Write config data to odr-config.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_config(key_path, config=None):
    """Access config value via dot-notation path.
    e.g. get_config("agent.search_agent_max_steps")
    """
    if config is None:
        config = load_config()
    keys = key_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value
