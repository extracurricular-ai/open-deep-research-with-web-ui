"""Tests for scripts/compaction.py — source ledger, L1 [S#] tagging, the L3
context-budget trimmer, and the DB-safety (emit-first) invariant."""

import types

from smolagents.memory import ActionStep, Timing, TokenUsage

from scripts import compaction as C

# --- helpers ---------------------------------------------------------------


def _astep(n, model_output=None, observations=None, tool_calls=None, input_tokens=None):
    s = ActionStep(step_number=n, timing=Timing(start_time=0.0, end_time=1.0))
    s.model_output = model_output
    s.observations = observations
    s.tool_calls = tool_calls
    if input_tokens is not None:
        s.token_usage = TokenUsage(input_tokens=input_tokens, output_tokens=0)
    return s


def _agent(steps):
    return types.SimpleNamespace(memory=types.SimpleNamespace(steps=steps))


# --- URL extraction --------------------------------------------------------


def test_extract_links_handles_both_formats_and_dedups():
    text = (
        "see [Title A](https://a.com/x) and |Title B](https://b.com/y) "
        "and https://a.com/x again and bare https://c.com"
    )
    links = C._extract_links(text, cap=50)
    urls = [u for u, _ in links]
    titles = dict(links)
    assert "https://a.com/x" in urls
    assert "https://b.com/y" in urls  # leading-pipe variant the search tools emit
    assert "https://c.com" in urls
    assert urls.count("https://a.com/x") == 1  # deduped by normalized URL
    assert titles["https://a.com/x"] == "Title A"
    assert titles["https://b.com/y"] == "Title B"


def test_extract_links_cap_is_a_floor_not_a_ceiling():
    text = " ".join(f"https://x{i}.com" for i in range(100))
    assert len(C._extract_links(text, cap=10)) == 10
    assert len(C._extract_links(text, cap=100)) == 100  # no hidden 30-style ceiling


# --- ledger ----------------------------------------------------------------


def test_ledger_stable_ids_and_title_upgrade():
    ag = _agent([])
    sid1 = C._ledger_add(ag, "https://a.com", "", 1)
    sid1b = C._ledger_add(ag, "https://a.com", "A Title", 3)  # same url, now titled
    sid2 = C._ledger_add(ag, "https://b.com", "", 2)  # different url
    assert sid1 == sid1b  # stable id, never reused
    assert sid2 != sid1
    entry = C._ledger(ag)["by_url"][C._normalize_url("https://a.com")]
    assert entry["title"] == "A Title"  # empty title upgraded in place


def test_render_ledger_never_evicts_referenced():
    ag = _agent([])
    for i in range(1, 11):
        C._ledger_add(ag, f"https://s{i}.com", "", i)
    enc = C._get_encoder("gpt-4o")
    referenced = {"S1", "S5", "S10"}
    block = C._render_ledger(
        ag, referenced, max_entries=3, max_tokens=4000, encoder=enc
    )
    # All referenced survive even though max_entries (3) < total (10).
    for sid in ("[S1]", "[S5]", "[S10]"):
        assert sid in block


# --- L1 summarizer ---------------------------------------------------------


def test_l1_summarizer_harvests_urls_and_appends_sources():
    # Fake model whose "summary" carries an inline [S1] tag.
    fake = types.SimpleNamespace(
        generate=lambda msgs: types.SimpleNamespace(
            content="Key fact about the topic [S1]."
        )
    )
    cb = C.make_per_step_summarizer(
        fake, "gpt-4o", threshold_tokens=5, summary_max_tokens=100
    )
    ag = _agent([])
    big_obs = "A big observation. Source: [Wiki](https://en.wikipedia.org/wiki/X). " + (
        "filler " * 80
    )
    step = _astep(1, observations=big_obs)
    cb(step, ag)
    assert step.observations.startswith(C.SUMMARY_PREFIX)
    assert "[S1]" in step.observations  # inline citation tag preserved
    assert "Sources:" in step.observations  # local resolution block
    assert "https://en.wikipedia.org/wiki/X" in step.observations
    assert any(
        "wikipedia.org/wiki/X" in e["url"] for e in C._ledger(ag)["by_url"].values()
    )


def test_l1_idempotent_on_already_summarized():
    fake = types.SimpleNamespace(
        generate=lambda msgs: types.SimpleNamespace(content="should not run")
    )
    cb = C.make_per_step_summarizer(fake, "gpt-4o", threshold_tokens=1)
    ag = _agent([])
    step = _astep(1, observations=f"{C.SUMMARY_PREFIX} already compacted")
    cb(step, ag)
    assert step.observations == f"{C.SUMMARY_PREFIX} already compacted"


# --- L3 budget trimmer -----------------------------------------------------


def test_l3_noop_when_under_budget():
    step = _astep(1, observations="x" * 100, input_tokens=100)
    ag = _agent([step])
    cb = C.make_memory_budget_trimmer(
        "gpt-4o", context_window=200000, reserve_tokens=20000
    )
    before = step.observations
    cb(step, ag)
    assert step.observations == before  # truth source says we fit -> untouched


def test_l3_trims_old_protects_recent_and_loses_no_url():
    steps = []
    for i in range(1, 9):
        obs = (
            f"{C.SUMMARY_PREFIX} (9000t orig) Finding {i} [S{i}]. "
            + ("word " * 1500)
            + f"\n\nSources: [S{i}] https://site{i}.com/page"
        )
        steps.append(
            _astep(
                i,
                model_output=("reasoning " * 400),
                observations=obs,
                input_tokens=(150000 if i == 8 else None),
            )
        )
    ag = _agent(steps)
    # Simulate L1 having harvested each step's URL into the ledger.
    for i in range(1, 9):
        C._ledger_add(ag, f"https://site{i}.com/page", "", i)

    cb = C.make_memory_budget_trimmer(
        "gpt-4o",
        context_window=131072,
        reserve_tokens=20000,
        trim_headroom_tokens=40000,
        keep_last_k=2,
        observation_max_tokens=50,
    )
    cb(steps[7], ag)  # step 8 (index 7) is over budget -> triggers

    # Recent keep_last_k=2 (indices 6,7) untouched.
    assert "word " * 100 in steps[7].observations
    assert isinstance(steps[6].model_output, str)
    assert not steps[6].model_output.startswith("[trimmed")

    # At least one old step had its model_output stubbed.
    assert any(
        isinstance(s.model_output, str) and s.model_output.startswith("[trimmed")
        for s in steps[:6]
    )

    # The global ledger is rendered onto a resident step.
    ledger_steps = [
        s for s in steps if s.observations and C.LEDGER_PREFIX in s.observations
    ]
    assert ledger_steps
    ledger_text = ledger_steps[0].observations
    # No citable URL lost: every old site#'s URL is resolvable via the ledger.
    for i in range(1, 7):
        assert f"site{i}.com/page" in ledger_text


def test_l3_keeps_tags_on_trimmed_step_even_when_url_dropped_locally():
    big = (
        f"{C.SUMMARY_PREFIX} (9000t orig) Important finding [S1]. "
        + ("token " * 3000)
        + "\n\nSources: [S1] https://only-here.com/p"
    )
    steps = [
        _astep(1, model_output="x", observations=big, input_tokens=150000),
        _astep(2, observations="recent", input_tokens=None),
        _astep(3, observations="recent2", input_tokens=None),
    ]
    ag = _agent(steps)
    C._ledger_add(ag, "https://only-here.com/p", "", 1)
    cb = C.make_memory_budget_trimmer(
        "gpt-4o",
        context_window=131072,
        reserve_tokens=20000,
        trim_headroom_tokens=0,
        keep_last_k=2,
        observation_max_tokens=20,
    )
    cb(steps[0], ag)
    # Step 1's prose was truncated, but its [S1] tag survives (attribution) and the
    # URL survives in the rendered ledger (availability).
    assert "[S1]" in steps[0].observations
    assert (
        "only-here.com/p" in steps[0].observations
    )  # ledger block lives here (anchor)


# --- DB-safety invariant ---------------------------------------------------


def test_emit_is_first_action_callback(monkeypatch):
    """on_action_step (the DB emitter) MUST be the first ActionStep callback so the
    DB captures full pre-compaction content before L1/L3 mutate memory."""
    import sys

    # Dummy keys so the model client constructs (no network call is made here).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    orig_stdout = sys.stdout
    try:
        import run  # noqa: E402  (import has module-level side effects)
        from config import load_config

        agent = run.create_agent(load_config())
        cbs = agent.step_callbacks._callbacks[ActionStep]
        assert cbs[0] is run.on_action_step
    finally:
        sys.stdout = orig_stdout
