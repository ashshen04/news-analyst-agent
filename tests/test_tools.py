"""Tests for tools.py — Tavily search with mocked client."""

from unittest.mock import patch


class TestSearchNews:
    def test_returns_formatted_results(self):
        fake_response = {
            "results": [
                {"title": "T1", "url": "https://example.com/1", "content": "C1"},
                {"title": "T2", "url": "https://news.org/2", "content": "C2"},
            ]
        }
        with patch("tools.client.search", return_value=fake_response):
            from tools import search_news

            results = search_news("AI")
            assert len(results) == 2
            assert results[0]["title"] == "T1"
            assert results[0]["source"] == "example.com"

    def test_returns_empty_on_error(self):
        with patch("tools.client.search", side_effect=Exception("API down")):
            from tools import search_news

            results = search_news("AI")
            assert results == []

    def test_respects_max_results(self):
        with patch("tools.client.search", return_value={"results": []}) as mock:
            from tools import search_news

            search_news("AI", max_results=3)
            _, kwargs = mock.call_args
            assert kwargs["max_results"] == 3
