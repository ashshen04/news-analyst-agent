"""Tests for daily.py — full pipeline integration with all externals mocked."""

import json
from unittest.mock import MagicMock, patch


class TestRunDaily:
    @patch("daily.archive_to_s3")
    @patch("daily.send_email")
    @patch("daily.graph")
    def test_full_run(self, mock_graph, mock_email, mock_s3, tmp_db, tmp_path):
        """Simulate a complete daily run with mocked graph and email."""
        # Prepare config
        config = {
            "topics": ["AI"],
            "email": {"to": "test@example.com"},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        # Mock graph.invoke to return a realistic result
        mock_graph.invoke.return_value = {
            "final_report": "# Report\nAll good.",
            "analysis": "Analysis text",
            "news_items": [{"title": "T", "url": "http://u", "source": "s", "content": "c"}],
        }

        with patch("builtins.open", return_value=open(config_path)):
            from daily import run_daily

            result = run_daily()

        assert result["topics"] == 1
        assert result["failed"] == 0
        mock_email.assert_called_once()

    @patch("daily.archive_to_s3")
    @patch("daily.send_email")
    @patch("daily.graph")
    def test_handles_topic_failure(self, mock_graph, mock_email, mock_s3, tmp_db, tmp_path):
        """One failing topic should not crash the entire run."""
        config = {
            "topics": ["AI", "Market"],
            "email": {"to": "test@example.com"},
        }
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(config))

        # First topic fails, second succeeds
        mock_graph.invoke.side_effect = [
            Exception("LLM down"),
            {
                "final_report": "Report",
                "analysis": "Analysis",
                "news_items": [],
            },
        ]

        with patch("builtins.open", return_value=open(config_path)):
            from daily import run_daily

            result = run_daily()

        assert result["topics"] == 1
        assert result["failed"] == 1
