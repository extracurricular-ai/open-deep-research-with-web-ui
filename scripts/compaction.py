"""LLM-based observation compaction + context-budget trimming for smolagents.

Three layers, registered together as step_callbacks:

  L1 (per-step, ActionStep): each large observation is summarized in-place. URLs
     are harvested into a per-agent global "source ledger" and the summary is asked
     to carry inline [S#] citation tags so per-claim attribution survives
     summarization. A compact local "Sources: [S#] url" block is appended so a
     still-resident step is self-contained.

  L2 (plan boundary, PlanningStep): old plan gaps are consolidated into one
     gap-summary, preserving [S#] tags; URLs are harvested into the ledger (no cap).

  L3 (budget fuse, ActionStep): the hard guarantee against context overflow. Reads
     the API-returned token_usage.input_tokens; when it approaches the model's
     context window (window - reserve) it trims the OLDEST non-protected steps —
     harvesting their URLs into the ledger FIRST (so no citation is lost), then
     stubbing model_output, dropping local URL blocks, and head/tail-truncating
     prose — down to a low watermark (hysteresis, so it fires rarely). The full
     [S#] -> URL ledger is rendered once onto the oldest resident step so every [S#]
     tag stays resolvable at final-answer time.

Reference safety: the final answer is produced by the model from in-context memory
ONLY (never the DB), so a URL the model cannot see cannot be cited. L3 therefore
never removes a URL without first recording it in the rendered ledger.

Token counting uses tiktoken (cl100k_base fallback) for *sizing* decisions; the
truth source for "are we near the window" is the API-returned input_tokens.

Smolagents callback timing: callbacks fire in _finalize_step BEFORE the new step is
appended to agent.memory.steps. run.py registers on_action_step (the DB emitter)
BEFORE these callbacks, so the DB always captures full, pre-compaction content while
the model is fed the compacted copy — the two never cross.
"""

import re
import sys
import time

import tiktoken
from smolagents.memory import ActionStep, PlanningStep
from smolagents.models import ChatMessage, MessageRole

URL_RE = re.compile(r"https?://[^\s)\]>'\"<]+", re.IGNORECASE)
# Markdown [title](url) AND the leading-pipe |title](url) variant the search tools
# emit (run.py MetaSota/Bocha/Tavily, scripts/text_web_browser.py SERP results).
MD_LINK_RE = re.compile(
    r"[\[|]([^\[\]|]{1,200})\]\((https?://[^\s)]+)\)", re.IGNORECASE
)
# A citation tag like [S3]; capturing variant yields the bare id "S3".
TAG_RE = re.compile(r"\[S\d+\]")
TAG_ID_RE = re.compile(r"\[(S\d+)\]")

SUMMARY_PREFIX = "[summary]"
GAP_SUMMARY_PREFIX = "[gap-summary]"
CONSOLIDATED_PREFIX = "[consolidated"
LEDGER_PREFIX = "[source-ledger]"
LEDGER_END = "[/source-ledger]"
LEDGER_RE = re.compile(r"\[source-ledger\][\s\S]*?\[/source-ledger\]\n*")
# Strip a step's local resolution block ("Sources: ..." / "URLs: ..." tail).
LOCAL_SOURCES_RE = re.compile(r"\n\nSources: |\nSources: |\nURLs(?: visited)?: ")


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


# ---------------------------------------------------------------------------
# URL handling + the per-agent source ledger
# ---------------------------------------------------------------------------


def _clean_url(u):
    return u.rstrip(".,;)]}'\"")


def _normalize_url(u):
    """Lowercase scheme+host only (preserve path/query case) so trivially-different
    spellings of the same URL dedupe, without over-merging distinct paths."""
    u = _clean_url(u)
    m = re.match(r"^(https?://[^/]+)(.*)$", u, re.IGNORECASE)
    if not m:
        return u
    return m.group(1).lower() + m.group(2)


def _extract_links(text, cap):
    """Return up to `cap` (url, title) pairs, deduped by normalized URL, order
    preserved. Markdown/pipe links contribute a title; bare URLs get an empty one."""
    if not text:
        return []
    out, seen = [], set()
    for title, url in MD_LINK_RE.findall(text):
        nu = _normalize_url(url)
        if nu not in seen:
            seen.add(nu)
            out.append((_clean_url(url), title.strip()[:200]))
            if len(out) >= cap:
                return out
    for url in URL_RE.findall(text):
        nu = _normalize_url(url)
        if nu not in seen:
            seen.add(nu)
            out.append((_clean_url(url), ""))
            if len(out) >= cap:
                return out
    return out


def _ledger(agent):
    """Lazily attach a per-agent source ledger. Keyed by normalized URL; stable,
    never-reused integer ids back the [S#] tags."""
    led = getattr(agent, "_source_ledger", None)
    if led is None:
        led = {"by_url": {}, "order": [], "counter": 0}
        agent._source_ledger = led
    return led


def _ledger_add(agent, url, title, step_no):
    """Add (or title-upgrade) a URL; return its stable "S#" id."""
    led = _ledger(agent)
    nu = _normalize_url(url)
    entry = led["by_url"].get(nu)
    if entry is None:
        led["counter"] += 1
        entry = {
            "id": led["counter"],
            "url": _clean_url(url),
            "title": (title or "")[:200],
            "first_step": step_no,
        }
        led["by_url"][nu] = entry
        led["order"].append(nu)
    elif title and not entry["title"]:
        entry["title"] = title[:200]
    return f"S{entry['id']}"


def _harvest(agent, text, step_no, cap):
    """Add every link in `text` to the ledger; return ordered (sid, url, title)."""
    out = []
    for url, title in _extract_links(text, cap):
        sid = _ledger_add(agent, url, title, step_no)
        out.append((sid, _clean_url(url), title))
    return out


def _find_tags(text):
    """Ordered, deduped bracketed tags like ['[S3]', '[S7]'] present in `text`."""
    return list(dict.fromkeys(TAG_RE.findall(text or "")))


def _referenced_sids(steps):
    """Set of bare ids ('S3') cited anywhere in resident memory (so the ledger
    renderer never evicts a source the model is still pointing at)."""
    ref = set()
    for s in steps:
        for fld in ("observations", "model_output"):
            v = getattr(s, fld, None)
            if v:
                ref.update(TAG_ID_RE.findall(v if isinstance(v, str) else str(v)))
    return ref


def _render_ledger(agent, referenced, max_entries, max_tokens, encoder):
    """Render the ledger as one block. Soft cap on entries (referenced entries are
    never dropped); titles dropped, then hard-truncated, if over the token budget."""
    led = _ledger(agent)
    nus = led["order"]
    if not nus:
        return ""
    if len(nus) > max_entries:
        ref_nus = [nu for nu in nus if f"S{led['by_url'][nu]['id']}" in referenced]
        unref = [nu for nu in nus if f"S{led['by_url'][nu]['id']}" not in referenced]
        # Referenced entries are NEVER evicted (citation correctness dominates the
        # cap); fill the rest with the most-recent unreferenced. k==0 must keep none
        # (note unref[-0:] would wrongly keep everything).
        k = max(0, max_entries - len(ref_nus))
        keep_unref = unref[-k:] if k > 0 else []
        keep = set(ref_nus) | set(keep_unref)
        nus = [nu for nu in nus if nu in keep]

    def line(nu, with_title):
        e = led["by_url"][nu]
        if with_title and e["title"]:
            return f"[S{e['id']}] {e['title']} — {e['url']}"
        return f"[S{e['id']}] {e['url']}"

    block = (
        LEDGER_PREFIX
        + "\n"
        + "\n".join(line(nu, True) for nu in nus)
        + "\n"
        + LEDGER_END
    )
    if _count_tokens(block, encoder) > max_tokens:
        block = (
            LEDGER_PREFIX
            + "\n"
            + "\n".join(line(nu, False) for nu in nus)
            + "\n"
            + LEDGER_END
        )
        if _count_tokens(block, encoder) > max_tokens:
            block = _truncate_to_tokens(block, max_tokens, encoder) + "\n" + LEDGER_END
    return block


def _attach_ledger(step, ledger_block):
    """Place/refresh the ledger block at the head of a step's observation
    (idempotent: any prior ledger block is stripped first)."""
    obs = getattr(step, "observations", "") or ""
    obs = LEDGER_RE.sub("", obs).lstrip("\n")
    step.observations = ledger_block + ("\n\n" + obs if obs else "")


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


# ---------------------------------------------------------------------------
# Layer 1 — per-step summarizer (ledger + inline [S#] aware)
# ---------------------------------------------------------------------------


def make_per_step_summarizer(
    model,
    main_model_id,
    threshold_tokens=1000,
    summary_max_tokens=600,
    summary_input_cap_tokens=6000,
    max_retries=10,
    ledger_harvest_cap=50,
):
    """ActionStep callback: replace step.observations with an LLM summary when the
    observation exceeds `threshold_tokens`. URLs are harvested into the agent ledger
    (built from the FULL pre-summary text) and the summary is asked to carry inline
    [S#] tags so per-claim attribution survives. A compact local 'Sources:' block is
    appended so a still-resident step resolves its own tags."""
    encoder = _get_encoder(main_model_id)

    def cb(step, agent):
        if not isinstance(step, ActionStep):
            return
        obs = step.observations
        if not obs:
            return
        # Idempotency: don't re-process our own outputs.
        if obs.startswith(
            (SUMMARY_PREFIX, GAP_SUMMARY_PREFIX, CONSOLIDATED_PREFIX, LEDGER_PREFIX)
        ):
            return

        obs_tokens = _count_tokens(obs, encoder)
        if obs_tokens < threshold_tokens:
            return

        # Harvest URLs from the FULL observation BEFORE trimming — this is the only
        # moment the URL is still adjacent to the text that cites it.
        harvested = _harvest(agent, obs, step.step_number, ledger_harvest_cap)
        trimmed = _trim_input_head_tail(obs, summary_input_cap_tokens, encoder)

        if harvested:
            table = "\n".join(f"  [{sid}] = {url}" for sid, url, _ in harvested)
            cite = (
                f"Cite sources inline: put the matching tag right after each fact "
                f"that came from it (do not invent tags). Available tags:\n{table}\n\n"
            )
        else:
            cite = ""

        prompt = (
            f"Summarize this tool observation in <={summary_max_tokens} tokens. "
            f"Preserve specific facts, numbers, names, dates, and key findings. "
            f"Skip navigation, repeated boilerplate, and empty HTML elements. "
            f"{cite}Output the summary text only, no preamble.\n\n"
            f"Observation:\n{trimmed}"
        )
        try:
            summary = _llm_call(
                model, prompt, summary_max_tokens, encoder, max_retries=max_retries
            )
        except Exception as e:
            # All retries exhausted. Fall back to head+tail token trim — better
            # than leaving the giant raw observation in memory.
            summary = _trim_input_head_tail(obs, summary_max_tokens, encoder)
            summary += (
                f" [summarizer failed after {max_retries} retries: {type(e).__name__}]"
            )

        sources = ""
        if harvested:
            sources = "\n\nSources: " + " | ".join(
                f"[{sid}] {url}" for sid, url, _ in harvested
            )
        step.observations = f"{SUMMARY_PREFIX} ({obs_tokens}t orig) {summary}{sources}"

    return cb


# ---------------------------------------------------------------------------
# Layer 2 — plan-boundary gap consolidator (tag-preserving, no URL caps)
# ---------------------------------------------------------------------------


def make_plan_consolidator(
    model,
    main_model_id,
    plan_keep_back=3,
    gap_summary_max_tokens=500,
    max_retries=10,
    ledger_harvest_cap=50,
):
    """PlanningStep callback: consolidate gaps older than `plan_keep_back` plans into
    one gap-summary on the gap's first ActionStep; stub the rest. [S#] tags are
    preserved and every URL is harvested into the ledger (no per-gap cap)."""
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
            return

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

        gap_lines, sids = [], []
        for i in action_indices:
            a = agent.memory.steps[i]
            if a.observations:
                line_text = _truncate_to_tokens(a.observations, 400, encoder)
                gap_lines.append(f"Step {a.step_number}: {line_text}")
                # No cap: never silently drop a URL before the ledger captures it.
                for sid, _, _ in _harvest(
                    agent, a.observations, a.step_number, ledger_harvest_cap
                ):
                    sids.append(sid)

        if not gap_lines:
            return

        first_step_no = agent.memory.steps[action_indices[0]].step_number
        last_step_no = agent.memory.steps[action_indices[-1]].step_number
        combined = "\n".join(gap_lines)
        prompt = (
            f"Below are summarized tool observations from research steps "
            f"{first_step_no}-{last_step_no}. Produce ONE condensed summary "
            f"in <={gap_summary_max_tokens} tokens capturing only the most "
            f"important findings and decisions. Synthesize across steps; do not "
            f"list per-step content. PRESERVE every [S#] citation tag attached to "
            f"a fact you carry forward. Output the summary text only.\n\n{combined}"
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

        seen = set()
        uniq = [s for s in sids if not (s in seen or seen.add(s))]
        sources_line = (
            f"\nSources: {' '.join('[' + s + ']' for s in uniq)}" if uniq else ""
        )
        agent.memory.steps[action_indices[0]].observations = (
            f"{GAP_SUMMARY_PREFIX} (steps {first_step_no}-{last_step_no}) "
            f"{consolidation}{sources_line}"
        )
        for i in action_indices[1:]:
            agent.memory.steps[
                i
            ].observations = f"{CONSOLIDATED_PREFIX} into step {first_step_no}]"

    return cb


# ---------------------------------------------------------------------------
# Layer 3 — context-budget trimmer (the hard overflow fuse)
# ---------------------------------------------------------------------------


def _trim_step(s, encoder, obs_max_tokens):
    """Stub model_output, drop the local URL/Sources block, head/tail-truncate prose
    — but keep any [S#] tags plus a compact 'Sources: [S#...]' line so the step still
    points at its sources (resolved via the global ledger). Returns tokens saved."""
    saved = 0

    mo = getattr(s, "model_output", None)
    if mo:
        mo_s = mo if isinstance(mo, str) else str(mo)
        if not mo_s.startswith("[trimmed"):
            tags = _find_tags(mo_s)
            stub = "[trimmed]" + (f" sources: {' '.join(tags)}" if tags else "")
            saved += _count_tokens(mo_s, encoder) - _count_tokens(stub, encoder)
            s.model_output = stub

    obs = getattr(s, "observations", None)
    if (
        obs
        and not obs.startswith(CONSOLIDATED_PREFIX)
        and not obs.startswith(LEDGER_PREFIX)
    ):
        before = _count_tokens(obs, encoder)
        tags = _find_tags(obs)
        body = LOCAL_SOURCES_RE.split(obs)[0]
        body = _truncate_to_tokens(body, obs_max_tokens, encoder)
        new = body + (f"\nSources: {' '.join(tags)}" if tags else "")
        after = _count_tokens(new, encoder)
        if after < before:
            s.observations = new
            saved += before - after

    return max(0, saved)


def make_memory_budget_trimmer(
    main_model_id,
    context_window,
    reserve_tokens=20000,
    trim_headroom_tokens=40000,
    keep_last_k=4,
    observation_max_tokens=300,
    ledger_harvest_cap=50,
    ledger_max_entries=200,
    ledger_render_max_tokens=4000,
):
    """ActionStep callback enforcing a hard context budget. When the API-returned
    input_tokens exceeds `context_window - reserve_tokens`, harvest every URL from
    the unprotected old steps into the ledger, then trim those steps (oldest first)
    until the estimated total drops to `budget - trim_headroom_tokens` (hysteresis,
    so it fires rarely → minimal prefix-cache churn). Finally render the full ledger
    onto the oldest resident step so every [S#] stays resolvable.

    The last `keep_last_k` steps and the system prompt/task are never touched, so the
    agent keeps recent context (with full URLs) and its goal."""
    encoder = _get_encoder(main_model_id)
    budget = max(1, context_window - reserve_tokens)
    target = max(1, budget - trim_headroom_tokens)

    def cb(step, agent):
        if not isinstance(step, ActionStep):
            return
        used = step.token_usage.input_tokens if step.token_usage else None
        if used is None or used <= budget:
            return  # API truth source says we still fit; do nothing.

        steps = agent.memory.steps
        n = len(steps)
        protected = set(range(max(0, n - keep_last_k), n))

        # 1) Harvest URLs from every UNPROTECTED step (all three serialized fields)
        #    BEFORE removing anything — guarantees no citable URL is lost.
        for i, s in enumerate(steps):
            if i in protected or not isinstance(s, ActionStep):
                continue
            for fld in ("model_output", "observations"):
                v = getattr(s, fld, None)
                if v:
                    _harvest(
                        agent,
                        v if isinstance(v, str) else str(v),
                        s.step_number,
                        ledger_harvest_cap,
                    )
            for tc in getattr(s, "tool_calls", None) or []:
                _harvest(
                    agent,
                    str(getattr(tc, "arguments", "")),
                    s.step_number,
                    ledger_harvest_cap,
                )

        # 2) Trim oldest unprotected steps until the estimate reaches the watermark.
        est = used
        anchor_idx = None
        for i, s in enumerate(steps):
            if est <= target:
                break
            if i in protected or not isinstance(s, ActionStep):
                continue
            if anchor_idx is None:
                anchor_idx = i
            est -= _trim_step(s, encoder, observation_max_tokens)

        # 3) Render the global ledger onto the oldest resident step so every [S#]
        #    cited in the (now trimmed) history resolves to a URL at answer time.
        if anchor_idx is None:
            anchor_idx = next(
                (i for i, s in enumerate(steps) if isinstance(s, ActionStep)), None
            )
        if anchor_idx is not None:
            referenced = _referenced_sids(steps)
            ledger_block = _render_ledger(
                agent,
                referenced,
                ledger_max_entries,
                ledger_render_max_tokens,
                encoder,
            )
            if ledger_block:
                _attach_ledger(steps[anchor_idx], ledger_block)

    return cb
