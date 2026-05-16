"""LLM-based observation compaction for smolagents agents.

Two layers, intended to be registered together as step_callbacks:

  Layer 1 (per-step, ActionStep callback):
    Each ActionStep's `observations` is summarized in-place by an LLM call
    right after the step finalizes. Raw HTML / page content never accumulates
    in agent memory; only summaries (configurable token budget) plus URL lists
    do.

  Layer 2 (plan boundary, PlanningStep callback):
    On each new PlanningStep, gaps older than `plan_keep_back` plans get
    consolidated: every ActionStep in the old gap has its (already-summarized)
    observation collapsed into a single gap-summary placed on the first step;
    the rest are stubbed to "[consolidated into step N]". Step objects, IDs,
    and step_numbers are preserved so SSE event references stay valid.

Token counting uses tiktoken with cl100k_base as the cross-model fallback
(~10-20% off real Anthropic/DeepSeek counts but good enough for trigger
decisions). The truth source for current LLM context size is the API-returned
`step.token_usage.input_tokens`; tiktoken is for sizing observation text we
can't otherwise measure.

Smolagents callback timing: callbacks fire in `_finalize_step` BEFORE the new
step is appended to `agent.memory.steps`, so this code accounts for that when
indexing.
"""

import re
import sys
import time

import tiktoken
from smolagents.memory import ActionStep, PlanningStep
from smolagents.models import ChatMessage, MessageRole

URL_RE = re.compile(r"https?://[^\s)\]>'\"<]+", re.IGNORECASE)

SUMMARY_PREFIX = "[summary]"
GAP_SUMMARY_PREFIX = "[gap-summary]"
CONSOLIDATED_PREFIX = "[consolidated"


def _get_encoder(model_id):
    """Best-effort tiktoken encoder. cl100k_base for unknown models."""
    try:
        return tiktoken.encoding_for_model(model_id)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def _count_tokens(text, encoder):
    if not text:
        return 0
    return len(encoder.encode(text))


def _truncate_to_tokens(text, max_tokens, encoder):
    """Hard cap output to N tokens."""
    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoder.decode(tokens[:max_tokens]) + " [...]"


def _trim_input_head_tail(text, max_tokens, encoder):
    """Head + tail token-based trim so a long observation can still be fed to the
    summarizer without exceeding its context. Preserves the most-important
    boundaries (page header + page footer / first results + last results)."""
    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    head = max_tokens * 3 // 4
    tail = max_tokens - head - 20
    elided = len(tokens) - head - tail
    return (
        encoder.decode(tokens[:head])
        + f"\n... [{elided} tokens elided] ...\n"
        + encoder.decode(tokens[-tail:])
    )


def _extract_urls(text, cap=30):
    if not text:
        return []
    out, seen = [], set()
    for u in URL_RE.findall(text):
        u = u.rstrip(".,;)")
        if u not in seen:
            out.append(u)
            seen.add(u)
            if len(out) >= cap:
                break
    return out


def _llm_call(model, prompt, output_max_tokens, encoder, max_retries=10):
    """Call the model with our own retry layer on top of whatever the model's
    internal retrier (rate-limit-only) handles. Default 10 attempts mirrors
    Claude Code's compaction retry budget. Exponential backoff capped at 30s."""
    msg = ChatMessage(
        role=MessageRole.USER,
        content=[{"type": "text", "text": prompt}],
    )
    last_exc = None
    for attempt in range(max_retries):
        try:
            out = model.generate([msg])
            txt = out.content if isinstance(out.content, str) else str(out.content)
            return _truncate_to_tokens(txt.strip(), output_max_tokens, encoder)
        except Exception as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = min(2**attempt, 30)
                print(
                    f"[compaction] LLM call failed (attempt {attempt + 1}/{max_retries}): "
                    f"{type(e).__name__}: {e}. Retrying in {delay}s.",
                    file=sys.stderr,
                )
                time.sleep(delay)
    raise last_exc


def make_per_step_summarizer(
    model,
    main_model_id,
    threshold_tokens=1000,
    summary_max_tokens=600,
    summary_input_cap_tokens=6000,
    max_retries=10,
):
    """Returns an ActionStep callback that replaces step.observations with a summary
    when the observation's token count exceeds `threshold_tokens`."""
    encoder = _get_encoder(main_model_id)

    def cb(step, agent):
        if not isinstance(step, ActionStep):
            return
        obs = step.observations
        if not obs:
            return
        # Idempotency.
        if (
            obs.startswith(SUMMARY_PREFIX)
            or obs.startswith(GAP_SUMMARY_PREFIX)
            or obs.startswith(CONSOLIDATED_PREFIX)
        ):
            return

        obs_tokens = _count_tokens(obs, encoder)
        if obs_tokens < threshold_tokens:
            return

        urls = _extract_urls(obs)
        trimmed = _trim_input_head_tail(obs, summary_input_cap_tokens, encoder)

        prompt = (
            f"Summarize this tool observation in <={summary_max_tokens} tokens. "
            f"Preserve specific facts, numbers, names, dates, and key findings. "
            f"Skip navigation, repeated boilerplate, and empty HTML elements. "
            f"Output the summary text only, no preamble.\n\n"
            f"Observation:\n{trimmed}"
        )
        try:
            summary = _llm_call(
                model, prompt, summary_max_tokens, encoder, max_retries=max_retries
            )
        except Exception as e:
            # All retries exhausted. Fall back to head+tail token trim — better
            # than leaving the giant raw observation in memory and blowing
            # context on the next step.
            summary = _trim_input_head_tail(obs, summary_max_tokens, encoder)
            summary += (
                f" [summarizer failed after {max_retries} retries: {type(e).__name__}]"
            )

        url_block = f"\n\nURLs: {urls}" if urls else ""
        step.observations = (
            f"{SUMMARY_PREFIX} ({obs_tokens}t orig) {summary}{url_block}"
        )

    return cb


def make_plan_consolidator(
    model,
    main_model_id,
    plan_keep_back=3,
    gap_summary_max_tokens=500,
    max_retries=10,
):
    """Returns a PlanningStep callback that consolidates gaps older than
    `plan_keep_back` plans into a single per-gap summary on the gap's first
    ActionStep. Other ActionSteps in the gap are stubbed."""
    encoder = _get_encoder(main_model_id)

    def cb(step, agent):
        if not isinstance(step, PlanningStep):
            return

        # Callback fires BEFORE the new plan is appended; account for that.
        pre_indices = [
            i for i, s in enumerate(agent.memory.steps) if isinstance(s, PlanningStep)
        ]
        current_idx = len(agent.memory.steps)
        post_indices = pre_indices + [current_idx]

        if len(post_indices) < plan_keep_back + 1:
            return  # not enough plans yet to consolidate anything

        # Gap to consolidate: ends at the (plan_keep_back+1)-from-last plan.
        gap_end = post_indices[-(plan_keep_back + 1)]
        if len(post_indices) >= plan_keep_back + 2:
            gap_start = post_indices[-(plan_keep_back + 2)] + 1
        else:
            gap_start = 0

        action_indices = [
            i
            for i in range(gap_start, gap_end)
            if isinstance(agent.memory.steps[i], ActionStep)
        ]
        if not action_indices:
            return

        first = agent.memory.steps[action_indices[0]]
        if first.observations and first.observations.startswith(GAP_SUMMARY_PREFIX):
            return  # gap already consolidated

        # Collect URLs and per-step summary lines from the (L1-summarized) gap.
        all_urls, seen_urls = [], set()
        gap_lines = []
        for i in action_indices:
            a = agent.memory.steps[i]
            if a.observations:
                # Token-trim each line so combined prompt stays bounded.
                line_text = _truncate_to_tokens(a.observations, 400, encoder)
                gap_lines.append(f"Step {a.step_number}: {line_text}")
                for u in _extract_urls(a.observations, cap=10):
                    if u not in seen_urls:
                        all_urls.append(u)
                        seen_urls.add(u)

        if not gap_lines:
            return

        first_step_no = agent.memory.steps[action_indices[0]].step_number
        last_step_no = agent.memory.steps[action_indices[-1]].step_number
        combined = "\n".join(gap_lines)
        prompt = (
            f"Below are summarized tool observations from research steps "
            f"{first_step_no}-{last_step_no}. Produce ONE condensed summary "
            f"in <={gap_summary_max_tokens} tokens capturing only the most "
            f"important findings and decisions. Synthesize across steps; do "
            f"not list per-step content. Output the summary text only.\n\n"
            f"{combined}"
        )
        try:
            consolidation = _llm_call(
                model, prompt, gap_summary_max_tokens, encoder, max_retries=max_retries
            )
        except Exception as e:
            consolidation = _truncate_to_tokens(
                combined, gap_summary_max_tokens, encoder
            )
            consolidation += f" [consolidator failed after {max_retries} retries: {type(e).__name__}]"

        url_block = f"\nURLs visited: {all_urls[:30]}" if all_urls else ""
        agent.memory.steps[action_indices[0]].observations = (
            f"{GAP_SUMMARY_PREFIX} (steps {first_step_no}-{last_step_no}) "
            f"{consolidation}{url_block}"
        )
        for i in action_indices[1:]:
            agent.memory.steps[i].observations = (
                f"{CONSOLIDATED_PREFIX} into step {first_step_no}]"
            )

    return cb
