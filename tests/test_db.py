"""Tests for db.py — SQLite persistence layer."""

from db import get_connection, get_recent_reports, get_run_history, save_report, save_run, update_run_status


class TestSaveRun:
    def test_returns_id(self, tmp_db):
        run_id = save_run("2026-03-31", 3)
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_default_status_is_success(self, tmp_db):
        run_id = save_run("2026-03-31", 2)
        conn = get_connection()
        row = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        assert row["status"] == "success"


class TestUpdateRunStatus:
    def test_changes_status(self, tmp_db):
        run_id = save_run("2026-03-31", 3)
        update_run_status(run_id, "partial")
        conn = get_connection()
        row = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
        conn.close()
        assert row["status"] == "partial"


class TestSaveReport:
    def test_saves_report_and_news(self, tmp_db, sample_news_items):
        run_id = save_run("2026-03-31", 1)
        report_id = save_report(
            run_id=run_id,
            topic="AI",
            analysis="Analysis text",
            final_report="Report text",
            elapsed=1.5,
            news_items=sample_news_items,
        )
        assert isinstance(report_id, int)

        conn = get_connection()
        news_rows = conn.execute(
            "SELECT * FROM news_items WHERE report_id = ?", (report_id,)
        ).fetchall()
        conn.close()
        assert len(news_rows) == len(sample_news_items)

    def test_news_count_stored(self, tmp_db, sample_news_items):
        run_id = save_run("2026-03-31", 1)
        report_id = save_report(
            run_id=run_id,
            topic="AI",
            analysis="a",
            final_report="r",
            elapsed=0.5,
            news_items=sample_news_items,
        )
        conn = get_connection()
        row = conn.execute("SELECT news_count FROM reports WHERE id = ?", (report_id,)).fetchone()
        conn.close()
        assert row["news_count"] == 2


class TestGetRecentReports:
    def test_returns_recent(self, tmp_db):
        run_id = save_run("2026-03-31", 1)
        save_report(run_id, "AI", "a", "r", 1.0, [])
        save_report(run_id, "AI", "a2", "r2", 2.0, [])
        rows = get_recent_reports("AI", limit=5)
        assert len(rows) == 2

    def test_filters_by_topic(self, tmp_db):
        run_id = save_run("2026-03-31", 2)
        save_report(run_id, "AI", "a", "r", 1.0, [])
        save_report(run_id, "Market", "a2", "r2", 2.0, [])
        rows = get_recent_reports("AI")
        assert len(rows) == 1
        assert rows[0]["topic"] == "AI"


class TestGetRunHistory:
    def test_returns_runs(self, tmp_db):
        save_run("2026-03-30", 2)
        save_run("2026-03-31", 3)
        rows = get_run_history(limit=10)
        assert len(rows) == 2
