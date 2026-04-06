"""Tests for feedback_collector.py — IMAP polling with mocked email."""

import email as email_module
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch


def _make_raw_email(subject: str, body: str, message_id: str = "<test@example.com>") -> bytes:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = "user@example.com"
    msg["Message-ID"] = message_id
    return msg.as_bytes()


class TestParseEmail:
    def test_structured_format(self, tmp_db):
        from feedback_collector import _parse_email
        raw = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Topic: AI Latest News\nRating: 5\nComment: Great depth!",
        )
        msg = email_module.message_from_bytes(raw)
        result = _parse_email(msg, ["AI Latest News", "Financial Market"])
        assert result is not None
        assert result.rating == 5
        assert result.topic == "AI Latest News"
        assert result.run_date == "2026-04-04"
        assert result.comment == "Great depth!"

    def test_missing_rating_returns_none(self, tmp_db):
        from feedback_collector import _parse_email
        raw = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Topic: AI Latest News\nNo rating here",
        )
        msg = email_module.message_from_bytes(raw)
        result = _parse_email(msg, ["AI Latest News"])
        assert result is None

    def test_non_reply_subject_returns_none(self, tmp_db):
        from feedback_collector import _parse_email
        raw = _make_raw_email("Daily News Report — 2026-04-04", "Rating: 4")
        msg = email_module.message_from_bytes(raw)
        result = _parse_email(msg, ["AI Latest News"])
        assert result is None

    def test_missing_topic_returns_none(self, tmp_db):
        from feedback_collector import _parse_email
        raw = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Rating: 4\nComment: Good",
        )
        msg = email_module.message_from_bytes(raw)
        result = _parse_email(msg, [])
        assert result is None

    def test_rating_with_out_of_5(self, tmp_db):
        from feedback_collector import _parse_email
        raw = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Topic: Financial Market\nRating: 3/5\nComment: Decent",
        )
        msg = email_module.message_from_bytes(raw)
        result = _parse_email(msg, ["Financial Market"])
        assert result is not None
        assert result.rating == 3

    def test_topic_matched_by_substring(self, tmp_db):
        from feedback_collector import _parse_email
        raw = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Topic: AI\nRating: 4",
        )
        msg = email_module.message_from_bytes(raw)
        result = _parse_email(msg, ["AI Latest News"])
        assert result is not None
        assert result.topic == "AI Latest News"


class TestExtractBody:
    def test_strips_quoted_lines(self, tmp_db):
        from feedback_collector import _extract_body
        raw = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Rating: 4\n\n> On April 4, you wrote:\n> Some quoted text",
        )
        msg = email_module.message_from_bytes(raw)
        body = _extract_body(msg)
        assert ">" not in body
        assert "Rating: 4" in body


class TestCollectFeedback:
    @patch("feedback_collector.imaplib.IMAP4_SSL")
    def test_saves_valid_feedback(self, mock_imap_cls, tmp_db):
        raw_email = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Topic: AI Latest News\nRating: 4\nComment: Very thorough!",
        )
        mock_mail = MagicMock()
        mock_imap_cls.return_value = mock_mail
        mock_mail.search.return_value = (None, [b"1"])
        mock_mail.fetch.return_value = (None, [(None, raw_email)])

        from feedback_collector import collect_feedback
        count = collect_feedback(known_topics=["AI Latest News"], lookback_days=7)
        assert count == 1

    @patch("feedback_collector.imaplib.IMAP4_SSL")
    def test_imap_failure_returns_zero(self, mock_imap_cls, tmp_db):
        mock_imap_cls.side_effect = Exception("IMAP down")
        from feedback_collector import collect_feedback
        count = collect_feedback(known_topics=["AI Latest News"])
        assert count == 0

    @patch("feedback_collector.imaplib.IMAP4_SSL")
    def test_deduplication_skips_seen_message_ids(self, mock_imap_cls, tmp_db):
        from db import save_feedback
        save_feedback("2026-04-04", "AI Latest News", 4, "test", "<test@example.com>")

        raw_email = _make_raw_email(
            "Re: Daily News Report — 2026-04-04",
            "Topic: AI Latest News\nRating: 4",
            message_id="<test@example.com>",
        )
        mock_mail = MagicMock()
        mock_imap_cls.return_value = mock_mail
        mock_mail.search.return_value = (None, [b"1"])
        mock_mail.fetch.return_value = (None, [(None, raw_email)])

        from feedback_collector import collect_feedback
        count = collect_feedback(known_topics=["AI Latest News"])
        assert count == 0

    @patch("feedback_collector.imaplib.IMAP4_SSL")
    def test_no_replies_returns_zero(self, mock_imap_cls, tmp_db):
        mock_mail = MagicMock()
        mock_imap_cls.return_value = mock_mail
        mock_mail.search.return_value = (None, [b""])

        from feedback_collector import collect_feedback
        count = collect_feedback(known_topics=["AI Latest News"])
        assert count == 0
