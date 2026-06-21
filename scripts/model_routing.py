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
    "deepseek-v4": "deepseek",
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

# Per-model metadata, sourced from LiteLLM model_prices_and_context_window.json and
# provider docs. Each entry is a tuple:
#
#   (context_window, max_output_tokens, input_cost_per_token, output_cost_per_token)
#
#   - context_window         : total input+output context window (max_input_tokens)
#   - max_output_tokens      : published max output cap (used to clamp max_completion_tokens)
#   - input_cost_per_token   : USD per input token (per-MTok / 1e6); None if not tracked
#   - output_cost_per_token  : USD per output token; None if not tracked
#
# Unknown models -> None (callers fall back to configured / default values).
# NOTE: prices drift; treat costs as best-effort. context_window/max_output drive
# correctness (context budgeting + output clamping) and are kept accurate.
_MODEL_INFO = {
    # --- Anthropic (200k context for all current Claude models) ---
    "claude-3-haiku-20240307": (200000, 4096, 2.5e-7, 1.25e-6),
    "claude-3-opus-20240229": (200000, 4096, 1.5e-5, 7.5e-5),
    "claude-3-5-haiku-20241022": (200000, 8192, 8e-7, 4e-6),
    "claude-3-5-sonnet-20241022": (200000, 8192, 3e-6, 1.5e-5),
    "claude-3-7-sonnet-20250219": (200000, 64000, 3e-6, 1.5e-5),
    "claude-4-opus-20250514": (200000, 32000, 1.5e-5, 7.5e-5),
    "claude-4-sonnet-20250514": (200000, 64000, 3e-6, 1.5e-5),
    "claude-haiku-4-5": (200000, 64000, 1e-6, 5e-6),
    "claude-haiku-4-5-20251001": (200000, 64000, 1e-6, 5e-6),
    "claude-opus-4-1": (200000, 32000, 1.5e-5, 7.5e-5),
    "claude-opus-4-1-20250805": (200000, 32000, 1.5e-5, 7.5e-5),
    "claude-opus-4-20250514": (200000, 32000, 1.5e-5, 7.5e-5),
    "claude-opus-4-5": (200000, 64000, 5e-6, 2.5e-5),
    "claude-opus-4-5-20251101": (200000, 64000, 5e-6, 2.5e-5),
    "claude-opus-4-6": (200000, 64000, 5e-6, 2.5e-5),
    "claude-opus-4-6-20260205": (200000, 64000, 5e-6, 2.5e-5),
    "claude-sonnet-4-20250514": (200000, 64000, 3e-6, 1.5e-5),
    "claude-sonnet-4-5": (200000, 64000, 3e-6, 1.5e-5),
    "claude-sonnet-4-5-20250929": (200000, 64000, 3e-6, 1.5e-5),
    "claude-sonnet-4-6": (200000, 64000, 3e-6, 1.5e-5),
    # --- DeepSeek (v3/chat-class: 128k; v4 series: 1M) ---
    "deepseek-chat": (131072, 8192, 2.7e-7, 1.1e-6),
    "deepseek-reasoner": (131072, 8192, 5.5e-7, 2.19e-6),
    "deepseek-coder": (131072, 8192, 2.7e-7, 1.1e-6),
    "deepseek-r1": (131072, 8192, 5.5e-7, 2.19e-6),
    "deepseek-v3": (131072, 8192, 2.7e-7, 1.1e-6),
    "deepseek-v3.2": (131072, 8192, 2.7e-7, 1.1e-6),
    "deepseek-v4": (1000000, 8192, None, None),
    # --- OpenAI ---
    "chatgpt-4o-latest": (128000, 16384, 5e-6, 1.5e-5),
    "gpt-3.5-turbo": (16385, 4096, 5e-7, 1.5e-6),
    "gpt-3.5-turbo-0125": (16385, 4096, 5e-7, 1.5e-6),
    "gpt-3.5-turbo-1106": (16385, 4096, 1e-6, 2e-6),
    "gpt-3.5-turbo-16k": (16385, 16384, 3e-6, 4e-6),
    "gpt-4": (8192, 8192, 3e-5, 6e-5),
    "gpt-4-0125-preview": (128000, 4096, 1e-5, 3e-5),
    "gpt-4-0314": (8192, 8192, 3e-5, 6e-5),
    "gpt-4-0613": (8192, 8192, 3e-5, 6e-5),
    "gpt-4-1106-preview": (128000, 4096, 1e-5, 3e-5),
    "gpt-4-turbo": (128000, 4096, 1e-5, 3e-5),
    "gpt-4-turbo-2024-04-09": (128000, 4096, 1e-5, 3e-5),
    "gpt-4-turbo-preview": (128000, 4096, 1e-5, 3e-5),
    "gpt-4.1": (1047576, 32768, 2e-6, 8e-6),
    "gpt-4.1-2025-04-14": (1047576, 32768, 2e-6, 8e-6),
    "gpt-4.1-mini": (1047576, 32768, 4e-7, 1.6e-6),
    "gpt-4.1-mini-2025-04-14": (1047576, 32768, 4e-7, 1.6e-6),
    "gpt-4.1-nano": (1047576, 32768, 1e-7, 4e-7),
    "gpt-4.1-nano-2025-04-14": (1047576, 32768, 1e-7, 4e-7),
    "gpt-4o": (128000, 4096, 2.5e-6, 1e-5),
    "gpt-4o-2024-05-13": (128000, 4096, 5e-6, 1.5e-5),
    "gpt-4o-2024-08-06": (128000, 16384, 2.5e-6, 1e-5),
    "gpt-4o-2024-11-20": (128000, 16384, 2.5e-6, 1e-5),
    "gpt-4o-mini": (128000, 16384, 1.5e-7, 6e-7),
    "gpt-4o-mini-2024-07-18": (128000, 16384, 1.5e-7, 6e-7),
    "gpt-4o-search-preview": (128000, 16384, 2.5e-6, 1e-5),
    "gpt-4o-search-preview-2025-03-11": (128000, 16384, 2.5e-6, 1e-5),
    "gpt-4o-mini-search-preview": (128000, 16384, 1.5e-7, 6e-7),
    "gpt-4o-mini-search-preview-2025-03-11": (128000, 16384, 1.5e-7, 6e-7),
    "gpt-5": (400000, 128000, 1.25e-6, 1e-5),
    "gpt-5-2025-08-07": (400000, 128000, 1.25e-6, 1e-5),
    "gpt-5-mini": (400000, 128000, 2.5e-7, 2e-6),
    "gpt-5-mini-2025-08-07": (400000, 128000, 2.5e-7, 2e-6),
    "gpt-5-nano": (400000, 128000, 5e-8, 4e-7),
    "gpt-5-nano-2025-08-07": (400000, 128000, 5e-8, 4e-7),
    "gpt-5-pro": (400000, 272000, None, None),
    "gpt-5-pro-2025-10-06": (400000, 272000, None, None),
    "gpt-5.1": (400000, 128000, 1.25e-6, 1e-5),
    "gpt-5.1-2025-11-13": (400000, 128000, 1.25e-6, 1e-5),
    "gpt-5.2": (400000, 128000, None, None),
    "gpt-5.2-2025-12-11": (400000, 128000, None, None),
    "gpt-5.2-pro": (400000, 272000, None, None),
    "gpt-5.2-pro-2025-12-11": (400000, 272000, None, None),
    "gpt-5.4": (400000, 128000, None, None),
    "gpt-5.4-2026-03-05": (400000, 128000, None, None),
    "gpt-5.4-mini": (400000, 128000, None, None),
    "gpt-5.4-nano": (400000, 128000, None, None),
    "gpt-5.4-pro": (400000, 272000, None, None),
    "gpt-5.4-pro-2026-03-05": (400000, 272000, None, None),
    "o1": (200000, 100000, 1.5e-5, 6e-5),
    "o1-2024-12-17": (200000, 100000, 1.5e-5, 6e-5),
    "o1-pro": (200000, 100000, 1.5e-4, 6e-4),
    "o1-pro-2025-03-19": (200000, 100000, 1.5e-4, 6e-4),
    "o3": (200000, 100000, 2e-6, 8e-6),
    "o3-2025-04-16": (200000, 100000, 2e-6, 8e-6),
    "o3-mini": (200000, 100000, 1.1e-6, 4.4e-6),
    "o3-mini-2025-01-31": (200000, 100000, 1.1e-6, 4.4e-6),
    "o3-pro": (200000, 100000, 2e-5, 8e-5),
    "o3-pro-2025-06-10": (200000, 100000, 2e-5, 8e-5),
    "o4-mini": (200000, 100000, 1.1e-6, 4.4e-6),
    "o4-mini-2025-04-16": (200000, 100000, 1.1e-6, 4.4e-6),
    "codex-mini-latest": (200000, 100000, 1.5e-6, 6e-6),
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


def _lookup_info(model_id: str):
    """Return the _MODEL_INFO tuple for a model_id, unwrapping a provider prefix.

    Mirrors get_model_routing: an explicit "provider/model" prefix is unwrapped
    first, then the bare ID is looked up. Returns None for unknown models.
    """
    bare = model_id.split("/", 1)[1] if "/" in model_id else model_id
    return _MODEL_INFO.get(bare)


def get_model_max_output_tokens(model_id: str) -> int | None:
    """Return the model's published max output tokens, or None if unknown.

    Unknown models return None so the caller's configured value is used as-is.
    """
    info = _lookup_info(model_id)
    return info[1] if info else None


def get_model_context_window(model_id: str) -> int | None:
    """Return the model's total context window (max input+output tokens), or None.

    Used by the Layer-3 budget trimmer to size the context budget. Unknown models
    return None so the caller falls back to compaction.default_context_window.
    """
    info = _lookup_info(model_id)
    return info[0] if info else None


def get_model_pricing(model_id: str) -> dict | None:
    """Return {"input_cost_per_token", "output_cost_per_token"} (USD/token), or None.

    Returns None when the model is unknown or pricing is not tracked for it.
    """
    info = _lookup_info(model_id)
    if not info or info[2] is None:
        return None
    return {"input_cost_per_token": info[2], "output_cost_per_token": info[3]}
