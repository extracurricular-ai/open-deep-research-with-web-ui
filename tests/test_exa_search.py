"""Unit tests for the Exa search provider integration."""

import sys
import types
from unittest.mock import MagicMock, patch

# Provide a minimal fake `exa_py` module so tests can run even if the
# package is not installed in the environment executing them.
if "exa_py" not in sys.modules:
    fake_exa_py = types.ModuleType("exa_py")

    class _FakeExa:
        def __init__(self, api_key=None, **kwargs):
            self.api_key = api_key
            self.headers = {}

        def search_and_contents(self, **kwargs):
            raise NotImplementedError

    fake_exa_py.Exa = _FakeExa
    sys.modules["exa_py"] = fake_exa_py

from run import ExaSearchTool, _extract_exa_snippet, get_search_tools  # noqa: E402


def _result(title="t", url="https://example.com", **fields):
    mock = MagicMock()
    mock.title = title
    mock.url = url
    for key in ("highlights", "summary", "text"):
        mock.__dict__[key] = fields.get(key)
    # configure_mock so getattr() returns the explicit values (including None)
    mock.configure_mock(
        highlights=fields.get("highlights"),
        summary=fields.get("summary"),
        text=fields.get("text"),
    )
    return mock


def test_extract_snippet_prefers_highlights():
    item = _result(
        highlights=["First insight", "Second insight"],
        summary="Summary should be ignored",
        text="Text should be ignored",
    )
    snippet = _extract_exa_snippet(item)
    assert "First insight" in snippet
    assert "Second insight" in snippet


def test_extract_snippet_falls_back_to_summary():
    item = _result(highlights=None, summary="This is the summary", text="text")
    assert _extract_exa_snippet(item) == "This is the summary"


def test_extract_snippet_falls_back_to_text():
    item = _result(highlights=None, summary=None, text="body text " * 200)
    snippet = _extract_exa_snippet(item)
    assert snippet.startswith("body text")
    # text is truncated to at most 1000 characters
    assert len(snippet) <= 1000


def test_extract_snippet_when_all_missing():
    item = _result(highlights=None, summary=None, text=None)
    assert _extract_exa_snippet(item) == "No description"


@patch("exa_py.Exa")
def test_sets_integration_header(mock_exa_cls):
    mock_client = MagicMock()
    mock_client.headers = {}
    mock_exa_cls.return_value = mock_client

    ExaSearchTool(api_key="test-key")

    assert (
        mock_client.headers.get("x-exa-integration")
        == "open-deep-research-with-web-ui"
    )


@patch("exa_py.Exa")
def test_forward_formats_results(mock_exa_cls):
    mock_client = MagicMock()
    mock_client.headers = {}
    response = MagicMock()
    response.results = [
        _result(
            title="OpenAI Research",
            url="https://openai.com/research",
            highlights=["Transformers changed NLP"],
        ),
        _result(
            title="Anthropic Paper",
            url="https://anthropic.com/paper",
            summary="A summary of the paper.",
        ),
    ]
    mock_client.search_and_contents.return_value = response
    mock_exa_cls.return_value = mock_client

    tool = ExaSearchTool(api_key="test-key", max_results=5)
    output = tool.forward("test query")

    call_kwargs = mock_client.search_and_contents.call_args.kwargs
    assert call_kwargs["query"] == "test query"
    assert call_kwargs["num_results"] == 5
    assert call_kwargs["type"] == "auto"
    assert "text" in call_kwargs
    assert "highlights" in call_kwargs

    assert "## Search Results (Exa)" in output
    assert "OpenAI Research" in output
    assert "https://openai.com/research" in output
    assert "Transformers changed NLP" in output
    assert "A summary of the paper." in output


@patch("exa_py.Exa")
def test_forward_passes_optional_filters(mock_exa_cls):
    mock_client = MagicMock()
    mock_client.headers = {}
    response = MagicMock()
    response.results = []
    mock_client.search_and_contents.return_value = response
    mock_exa_cls.return_value = mock_client

    tool = ExaSearchTool(
        api_key="test-key",
        search_type="neural",
        category="research paper",
        include_domains=["arxiv.org"],
        exclude_domains=["example.com"],
        start_published_date="2026-01-01",
        end_published_date="2026-04-01",
    )
    tool.forward("transformers")

    kwargs = mock_client.search_and_contents.call_args.kwargs
    assert kwargs["type"] == "neural"
    assert kwargs["category"] == "research paper"
    assert kwargs["include_domains"] == ["arxiv.org"]
    assert kwargs["exclude_domains"] == ["example.com"]
    assert kwargs["start_published_date"] == "2026-01-01"
    assert kwargs["end_published_date"] == "2026-04-01"


@patch("exa_py.Exa")
def test_forward_handles_empty_results(mock_exa_cls):
    mock_client = MagicMock()
    mock_client.headers = {}
    response = MagicMock()
    response.results = []
    mock_client.search_and_contents.return_value = response
    mock_exa_cls.return_value = mock_client

    tool = ExaSearchTool(api_key="test-key")
    assert tool.forward("anything") == "No results found."


@patch("exa_py.Exa")
def test_forward_catches_exceptions(mock_exa_cls):
    mock_client = MagicMock()
    mock_client.headers = {}
    mock_client.search_and_contents.side_effect = RuntimeError("boom")
    mock_exa_cls.return_value = mock_client

    tool = ExaSearchTool(api_key="test-key")
    output = tool.forward("q")
    assert output.startswith("Error performing search:")
    assert "boom" in output


@patch("exa_py.Exa")
def test_get_search_tools_selects_exa_when_key_present(mock_exa_cls):
    mock_exa_cls.return_value = MagicMock(headers={})
    cfg = {
        "search": {
            "providers": [{"provider": "EXA", "key": "cfg-key"}],
            "max_results": 7,
        }
    }
    tools = get_search_tools(cfg)
    assert len(tools) == 1
    assert isinstance(tools[0], ExaSearchTool)
    assert tools[0].max_results == 7


def test_get_search_tools_skips_exa_when_key_missing(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    cfg = {
        "search": {
            "providers": [
                {"provider": "EXA", "key": ""},
                {"provider": "DDGS", "key": ""},
            ],
            "max_results": 10,
        }
    }
    tools = get_search_tools(cfg)
    # Falls through to DDGS when EXA key is missing
    assert len(tools) == 1
    assert not isinstance(tools[0], ExaSearchTool)


@patch("exa_py.Exa")
def test_get_search_tools_uses_env_var_fallback(mock_exa_cls, monkeypatch):
    mock_exa_cls.return_value = MagicMock(headers={})
    monkeypatch.setenv("EXA_API_KEY", "env-key")
    cfg = {
        "search": {
            "providers": [{"provider": "EXA", "key": ""}],
            "max_results": 10,
        }
    }
    tools = get_search_tools(cfg)
    assert len(tools) == 1
    assert isinstance(tools[0], ExaSearchTool)
    mock_exa_cls.assert_called_with(api_key="env-key")
