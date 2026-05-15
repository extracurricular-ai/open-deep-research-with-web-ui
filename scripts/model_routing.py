"""Model name -> provider routing.

Mirrors LiteLLM's routing logic: exact name lookup -> prefix fallback -> default.

The _MODEL_PROVIDER_MAP is sourced from LiteLLM's model_prices_and_context_window.json
for the openai, anthropic, and deepseek providers (chat models only).
"""

# ---------------------------------------------------------------------------
# Model name -> provider registry
#
# Priority order:
#   1. Explicit "provider/model" prefix  (e.g. "anthropic/claude-...")
#   2. Exact match in _MODEL_PROVIDER_MAP
#   3. Prefix match in _MODEL_PREFIX_ROUTES
#   4. Default -> "openai"
# ---------------------------------------------------------------------------
_MODEL_PROVIDER_MAP = {
    # --- Anthropic ---
    "claude-3-7-sonnet-20250219": "anthropic",
    "claude-3-haiku-20240307": "anthropic",
    "claude-3-opus-20240229": "anthropic",
    "claude-3-5-haiku-20241022": "anthropic",
    "claude-3-5-sonnet-20241022": "anthropic",
    "claude-4-opus-20250514": "anthropic",
    "claude-4-sonnet-20250514": "anthropic",
    "claude-haiku-4-5": "anthropic",
    "claude-haiku-4-5-20251001": "anthropic",
    "claude-opus-4-1": "anthropic",
    "claude-opus-4-1-20250805": "anthropic",
    "claude-opus-4-20250514": "anthropic",
    "claude-opus-4-5": "anthropic",
    "claude-opus-4-5-20251101": "anthropic",
    "claude-opus-4-6": "anthropic",
    "claude-opus-4-6-20260205": "anthropic",
    "claude-sonnet-4-20250514": "anthropic",
    "claude-sonnet-4-5": "anthropic",
    "claude-sonnet-4-5-20250929": "anthropic",
    "claude-sonnet-4-6": "anthropic",
    # --- DeepSeek ---
    "deepseek-chat": "deepseek",
    "deepseek-reasoner": "deepseek",
    "deepseek-coder": "deepseek",
    "deepseek-r1": "deepseek",
    "deepseek-v3": "deepseek",
    "deepseek-v3.2": "deepseek",
    # --- OpenAI (chat-relevant subset) ---
    "chatgpt-4o-latest": "openai",
    "gpt-3.5-turbo": "openai",
    "gpt-3.5-turbo-0125": "openai",
    "gpt-3.5-turbo-1106": "openai",
    "gpt-3.5-turbo-16k": "openai",
    "gpt-4": "openai",
    "gpt-4-0125-preview": "openai",
    "gpt-4-0314": "openai",
    "gpt-4-0613": "openai",
    "gpt-4-1106-preview": "openai",
    "gpt-4-turbo": "openai",
    "gpt-4-turbo-2024-04-09": "openai",
    "gpt-4-turbo-preview": "openai",
    "gpt-4.1": "openai",
    "gpt-4.1-2025-04-14": "openai",
    "gpt-4.1-mini": "openai",
    "gpt-4.1-mini-2025-04-14": "openai",
    "gpt-4.1-nano": "openai",
    "gpt-4.1-nano-2025-04-14": "openai",
    "gpt-4o": "openai",
    "gpt-4o-2024-05-13": "openai",
    "gpt-4o-2024-08-06": "openai",
    "gpt-4o-2024-11-20": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4o-mini-2024-07-18": "openai",
    "gpt-4o-search-preview": "openai",
    "gpt-4o-search-preview-2025-03-11": "openai",
    "gpt-4o-mini-search-preview": "openai",
    "gpt-4o-mini-search-preview-2025-03-11": "openai",
    "gpt-5": "openai",
    "gpt-5-2025-08-07": "openai",
    "gpt-5-mini": "openai",
    "gpt-5-mini-2025-08-07": "openai",
    "gpt-5-nano": "openai",
    "gpt-5-nano-2025-08-07": "openai",
    "gpt-5-pro": "openai",
    "gpt-5-pro-2025-10-06": "openai",
    "gpt-5.1": "openai",
    "gpt-5.1-2025-11-13": "openai",
    "gpt-5.2": "openai",
    "gpt-5.2-2025-12-11": "openai",
    "gpt-5.2-pro": "openai",
    "gpt-5.2-pro-2025-12-11": "openai",
    "gpt-5.4": "openai",
    "gpt-5.4-2026-03-05": "openai",
    "gpt-5.4-mini": "openai",
    "gpt-5.4-nano": "openai",
    "gpt-5.4-pro": "openai",
    "gpt-5.4-pro-2026-03-05": "openai",
    "o1": "openai",
    "o1-2024-12-17": "openai",
    "o1-pro": "openai",
    "o1-pro-2025-03-19": "openai",
    "o3": "openai",
    "o3-2025-04-16": "openai",
    "o3-mini": "openai",
    "o3-mini-2025-01-31": "openai",
    "o3-pro": "openai",
    "o3-pro-2025-06-10": "openai",
    "o4-mini": "openai",
    "o4-mini-2025-04-16": "openai",
    "codex-mini-latest": "openai",
}

# Prefix-based fallback: checked in order when model is not in _MODEL_PROVIDER_MAP.
_MODEL_PREFIX_ROUTES = [
    ("claude", "anthropic"),
    ("deepseek", "deepseek"),
    ("gpt-", "openai"),
    ("gpt3", "openai"),
    ("gpt4", "openai"),
    ("chatgpt", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("o4", "openai"),
    ("ft:gpt-", "openai"),
    ("ft:o", "openai"),
]

PROVIDER_API_BASES = {
    "deepseek": "https://api.deepseek.com/v1",
}

# Per-model max output tokens (sourced from LiteLLM model_prices_and_context_window
# and provider docs). Used to clamp the user-configured max_completion_tokens so
# we don't 4xx on small-cap models when a research-friendly default is set.
# Unknown models -> None (no cap, configured value passes through unchanged).
_MODEL_MAX_OUTPUT_TOKENS = {
    # --- Anthropic (standard caps; extended-thinking caps not used here) ---
    "claude-3-haiku-20240307": 4096,
    "claude-3-opus-20240229": 4096,
    "claude-3-5-haiku-20241022": 8192,
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-7-sonnet-20250219": 64000,
    "claude-4-opus-20250514": 32000,
    "claude-4-sonnet-20250514": 64000,
    "claude-haiku-4-5": 64000,
    "claude-haiku-4-5-20251001": 64000,
    "claude-opus-4-1": 32000,
    "claude-opus-4-1-20250805": 32000,
    "claude-opus-4-20250514": 32000,
    "claude-opus-4-5": 64000,
    "claude-opus-4-5-20251101": 64000,
    "claude-opus-4-6": 64000,
    "claude-opus-4-6-20260205": 64000,
    "claude-sonnet-4-20250514": 64000,
    "claude-sonnet-4-5": 64000,
    "claude-sonnet-4-5-20250929": 64000,
    "claude-sonnet-4-6": 64000,
    # --- DeepSeek ---
    "deepseek-chat": 8192,
    "deepseek-coder": 8192,
    "deepseek-reasoner": 8192,
    "deepseek-r1": 8192,
    "deepseek-v3": 8192,
    "deepseek-v3.2": 8192,
    # --- OpenAI ---
    "chatgpt-4o-latest": 16384,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-0125": 4096,
    "gpt-3.5-turbo-1106": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-4": 8192,
    "gpt-4-0125-preview": 4096,
    "gpt-4-0314": 8192,
    "gpt-4-0613": 8192,
    "gpt-4-1106-preview": 4096,
    "gpt-4-turbo": 4096,
    "gpt-4-turbo-2024-04-09": 4096,
    "gpt-4-turbo-preview": 4096,
    "gpt-4.1": 32768,
    "gpt-4.1-2025-04-14": 32768,
    "gpt-4.1-mini": 32768,
    "gpt-4.1-mini-2025-04-14": 32768,
    "gpt-4.1-nano": 32768,
    "gpt-4.1-nano-2025-04-14": 32768,
    "gpt-4o": 4096,
    "gpt-4o-2024-05-13": 4096,
    "gpt-4o-2024-08-06": 16384,
    "gpt-4o-2024-11-20": 16384,
    "gpt-4o-mini": 16384,
    "gpt-4o-mini-2024-07-18": 16384,
    "gpt-4o-search-preview": 16384,
    "gpt-4o-search-preview-2025-03-11": 16384,
    "gpt-4o-mini-search-preview": 16384,
    "gpt-4o-mini-search-preview-2025-03-11": 16384,
    "gpt-5": 128000,
    "gpt-5-2025-08-07": 128000,
    "gpt-5-mini": 128000,
    "gpt-5-mini-2025-08-07": 128000,
    "gpt-5-nano": 128000,
    "gpt-5-nano-2025-08-07": 128000,
    "gpt-5-pro": 272000,
    "gpt-5-pro-2025-10-06": 272000,
    "gpt-5.1": 128000,
    "gpt-5.1-2025-11-13": 128000,
    "gpt-5.2": 128000,
    "gpt-5.2-2025-12-11": 128000,
    "gpt-5.2-pro": 272000,
    "gpt-5.2-pro-2025-12-11": 272000,
    "gpt-5.4": 128000,
    "gpt-5.4-2026-03-05": 128000,
    "gpt-5.4-mini": 128000,
    "gpt-5.4-nano": 128000,
    "gpt-5.4-pro": 272000,
    "gpt-5.4-pro-2026-03-05": 272000,
    "o1": 100000,
    "o1-2024-12-17": 100000,
    "o1-pro": 100000,
    "o1-pro-2025-03-19": 100000,
    "o3": 100000,
    "o3-2025-04-16": 100000,
    "o3-mini": 100000,
    "o3-mini-2025-01-31": 100000,
    "o3-pro": 100000,
    "o3-pro-2025-06-10": 100000,
    "o4-mini": 100000,
    "o4-mini-2025-04-16": 100000,
    "codex-mini-latest": 100000,
}


def get_model_routing(model_id: str) -> dict:
    """Return provider, bare model ID, and optional api_base for a model_id.

    Routing priority:
      1. Explicit 'provider/model' prefix (e.g. 'anthropic/claude-sonnet-4')
      2. Exact match in _MODEL_PROVIDER_MAP
      3. Prefix match in _MODEL_PREFIX_ROUTES
      4. Default -> openai
    """
    # 1. Explicit provider prefix
    if "/" in model_id:
        parts = model_id.split("/", 1)
        explicit_provider = parts[0].lower()
        bare = parts[1]
        result = {"provider": explicit_provider, "bare_id": bare}
        if explicit_provider in PROVIDER_API_BASES:
            result["api_base"] = PROVIDER_API_BASES[explicit_provider]
        return result

    # 2. Exact name lookup
    bare = model_id
    provider = _MODEL_PROVIDER_MAP.get(bare)
    if provider:
        result = {"provider": provider, "bare_id": bare}
        if provider in PROVIDER_API_BASES:
            result["api_base"] = PROVIDER_API_BASES[provider]
        return result

    # 3. Prefix fallback
    for prefix, prov in _MODEL_PREFIX_ROUTES:
        if bare.startswith(prefix):
            result = {"provider": prov, "bare_id": bare}
            if prov in PROVIDER_API_BASES:
                result["api_base"] = PROVIDER_API_BASES[prov]
            return result

    # 4. Default to openai
    return {"provider": "openai", "bare_id": bare}


def get_model_max_output_tokens(model_id: str) -> int | None:
    """Return the model's published max output tokens, or None if unknown.

    Lookup mirrors get_model_routing: an explicit "provider/model" prefix is
    unwrapped first, then the bare ID is looked up in _MODEL_MAX_OUTPUT_TOKENS.
    Unknown models return None so the caller's configured value is used as-is.
    """
    bare = model_id.split("/", 1)[1] if "/" in model_id else model_id
    return _MODEL_MAX_OUTPUT_TOKENS.get(bare)
