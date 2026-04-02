"""Tests for daily.py — full pipeline integration with all externals mocked."""

from unittest.mock import patch


class TestRunDaily:
    @patch("daily.archive_to_s3")
    @patch("daily.send_email")
    @patch("daily.graph")
    def test_full_run(self, mock_graph, mock_email, mock_s3, tmp_db, monkeypatch):
        """Simulate a complete daily run with mocked graph and email."""
        monkeypatch.setenv("TOPICS", "AI")
        monkeypatch.setenv("EMAIL_TO", "test@example.com")

        mock_graph.invoke.return_value = {
            "final_report": "# Report\nAll good.",
            "analysis": "Analysis text",
            "news_items": [{"title": "T", "url": "http://u", "source": "s", "content": "c"}],
        }

        from daily import run_daily

        result = run_daily()

        assert result["topics"] == 1
        assert result["failed"] == 0
        mock_email.assert_called_once()

    @patch("daily.archive_to_s3")
    @patch("daily.send_email")
    @patch("daily.graph")
    def test_handles_topic_failure(self, mock_graph, mock_email, mock_s3, tmp_db, monkeypatch):
        """One failing topic should not crash the entire run."""
        monkeypatch.setenv("TOPICS", "AI,Market")
        monkeypatch.setenv("EMAIL_TO", "test@example.com")

        mock_graph.invoke.side_effect = [
            Exception("LLM down"),
            {
                "final_report": "Report",
                "analysis": "Analysis",
                "news_items": [],
            },
        ]

        from daily import run_daily

        result = run_daily()

        assert result["topics"] == 1
        assert result["failed"] == 1
