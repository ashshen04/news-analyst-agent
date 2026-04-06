"""Tests for nodes.py — LLM node functions with mocked Groq."""

from unittest.mock import MagicMock, call, patch

import pytest

from langchain_groq import ChatGroq
from nodes import analyze_news, fetch_news, find_conflicts, generate_report, invoke_with_retry


@pytest.fixture
def mock_llm():
    """Patch ChatGroq.invoke at the class level to return a fake response."""
    fake_resp = MagicMock()
    fake_resp.content = "Mocked LLM response."
    with patch.object(ChatGroq, "invoke", return_value=fake_resp) as m:
        yield m


@pytest.fixture
def mock_search():
    """Patch nodes.search_news to return sample articles."""
    from tests.conftest import SAMPLE_NEWS_ITEMS

    with patch("nodes.search_news", return_value=SAMPLE_NEWS_ITEMS) as m:
        yield m


class TestInvokeWithRetry:
    def test_returns_content(self, mock_llm):
        result = invoke_with_retry("Hello")
        assert result == "Mocked LLM response."
        mock_llm.assert_called_once()

    def test_retries_on_rate_limit(self, mock_llm):
        from groq import RateLimitError

        err = RateLimitError(
            message="rate limit",
            response=MagicMock(status_code=429, headers={}),
            body=None,
        )
        mock_llm.side_effect = [err, MagicMock(content="ok")]
        result = invoke_with_retry("Hello", max_retries=2, wait=0)
        assert result == "ok"
        assert mock_llm.call_count == 2


class TestFetchNews:
    def test_returns_items_and_increments(self, mock_search, sample_state):
        sample_state["iterations"] = 0
        result = fetch_news(sample_state)
        assert len(result["news_items"]) == 2
        assert result["iterations"] == 1


class TestAnalyzeNews:
    def test_returns_analysis(self, mock_llm, sample_state):
        result = analyze_news(sample_state)
        assert result["analysis"] == "Mocked LLM response."


class TestFindConflicts:
    def test_parses_lines(self, mock_llm, sample_state):
        mock_llm.return_value.content = "- Conflict A\n- Conflict B"
        result = find_conflicts(sample_state)
        assert len(result["conflicts"]) == 2
        assert "Conflict A" in result["conflicts"][0]


class TestGenerateReport:
    def test_returns_report(self, mock_llm, sample_state):
        with patch("rag.retrieve_examples", return_value=[]):
            result = generate_report(sample_state)
        assert result["final_report"] == "Mocked LLM response."

    def test_injects_rag_examples_into_prompt(self, mock_llm, sample_state):
        fake_example = {
            "final_report": "## Executive Summary\nSample past report.",
            "topic": "AI Trends",
            "rating": 5,
            "run_date": "2026-04-01",
        }
        with patch("rag.retrieve_examples", return_value=[fake_example]):
            generate_report(sample_state)
        call_args = mock_llm.call_args[0][0]
        prompt_text = str(call_args)
        assert "Well-Received Past Reports" in prompt_text
        assert "AI Trends" in prompt_text

    def test_no_prefix_when_no_examples(self, mock_llm, sample_state):
        with patch("rag.retrieve_examples", return_value=[]):
            generate_report(sample_state)
        call_args = mock_llm.call_args[0][0]
        prompt_text = str(call_args)
        assert "Well-Received Past Reports" not in prompt_text
