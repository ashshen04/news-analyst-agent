"""Tests for feedback-related db.py functions."""

import sqlite3

import pytest


class TestSaveFeedback:
    def test_saves_without_report_link(self, tmp_db):
        from db import save_feedback
        fid = save_feedback("2026-04-04", "AI Latest News", 4, "Good report")
        assert isinstance(fid, int)
        assert fid > 0

    def test_links_to_report_when_exists(self, tmp_db, sample_news_items):
        from db import get_connection, save_feedback, save_report, save_run
        run_id = save_run("2026-04-04", 1)
        report_id = save_report(run_id, "AI Latest News", "analysis", "final", 1.0, sample_news_items)
        fid = save_feedback("2026-04-04", "AI Latest News", 5, "Excellent")
        conn = get_connection()
        row = conn.execute("SELECT report_id FROM feedback WHERE id = ?", (fid,)).fetchone()
        conn.close()
        assert row["report_id"] == report_id

    def test_rejects_rating_above_5(self, tmp_db):
        from db import save_feedback
        with pytest.raises(sqlite3.IntegrityError):
            save_feedback("2026-04-04", "AI", 6)

    def test_rejects_rating_below_1(self, tmp_db):
        from db import save_feedback
        with pytest.raises(sqlite3.IntegrityError):
            save_feedback("2026-04-04", "AI", 0)

    def test_stores_email_message_id(self, tmp_db):
        from db import get_connection, save_feedback
        save_feedback("2026-04-04", "AI", 3, None, "<msg123@example.com>")
        conn = get_connection()
        row = conn.execute("SELECT email_message_id FROM feedback").fetchone()
        conn.close()
        assert row["email_message_id"] == "<msg123@example.com>"


class TestGetFeedbackRatings:
    def test_returns_empty_for_no_ids(self, tmp_db):
        from db import get_feedback_ratings
        assert get_feedback_ratings([]) == {}

    def test_returns_ratings_for_known_ids(self, tmp_db, sample_news_items):
        from db import get_feedback_ratings, save_feedback, save_report, save_run
        run_id = save_run("2026-04-04", 1)
        report_id = save_report(run_id, "AI", "a", "r", 1.0, sample_news_items)
        save_feedback("2026-04-04", "AI", 4, "Good", None)
        ratings = get_feedback_ratings([report_id])
        assert ratings[report_id] == 4

    def test_uses_max_rating_for_multiple_feedback(self, tmp_db, sample_news_items):
        from db import get_feedback_ratings, save_feedback, save_report, save_run
        run_id = save_run("2026-04-04", 1)
        report_id = save_report(run_id, "AI", "a", "r", 1.0, sample_news_items)
        save_feedback("2026-04-04", "AI", 3, "Okay")
        save_feedback("2026-04-04", "AI", 5, "Perfect")
        ratings = get_feedback_ratings([report_id])
        assert ratings[report_id] == 5

    def test_ignores_unknown_ids(self, tmp_db):
        from db import get_feedback_ratings
        ratings = get_feedback_ratings([9999])
        assert 9999 not in ratings


class TestGetRecentFeedback:
    def test_returns_only_items_with_comments(self, tmp_db):
        from db import get_recent_feedback, save_feedback
        save_feedback("2026-04-04", "AI", 4, "Great depth")
        save_feedback("2026-04-04", "Market", 3, None)
        items = get_recent_feedback()
        assert len(items) == 1
        assert items[0]["topic"] == "AI"

    def test_respects_limit(self, tmp_db):
        from db import get_recent_feedback, save_feedback
        for i in range(5):
            save_feedback("2026-04-04", "AI", 4, f"Comment {i}")
        items = get_recent_feedback(limit=3)
        assert len(items) == 3


class TestCountFeedbackSinceLastSynthesis:
    def test_returns_total_when_no_synthesis(self, tmp_db):
        from db import count_feedback_since_last_synthesis, save_feedback
        save_feedback("2026-04-04", "AI", 4, "Good")
        save_feedback("2026-04-04", "AI", 3, "Okay")
        assert count_feedback_since_last_synthesis() == 2

    def test_returns_zero_after_synthesis(self, tmp_db):
        from db import count_feedback_since_last_synthesis, save_feedback, save_synthesis_log
        save_feedback("2026-04-04", "AI", 4, "Good")
        save_synthesis_log(1, "- Be concise")
        assert count_feedback_since_last_synthesis() == 0
