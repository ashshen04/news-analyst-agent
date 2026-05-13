"""Tests for the dedup + digest helpers in db.py."""

from db import (
    get_latest_digest,
    get_seen_fingerprints,
    save_report,
    save_run,
    title_hash,
)


class TestTitleHash:
    def test_case_insensitive(self):
        assert title_hash("Hello World") == title_hash("hello world")

    def test_punctuation_stripped(self):
        assert title_hash("AI: A Breakthrough!") == title_hash("ai a breakthrough")

    def test_different_titles_differ(self):
        assert title_hash("AI breakthrough") != title_hash("market update")

    def test_empty_safe(self):
        assert title_hash("") == title_hash("")


class TestGetLatestDigest:
    def test_returns_none_when_missing(self, tmp_db):
        assert get_latest_digest("AI") is None

    def test_skips_empty_digests(self, tmp_db, sample_news_items):
        run_id = save_run("2026-05-10", 1)
        save_report(run_id, "AI", "a", "r", 1.0, sample_news_items, digest="")
        assert get_latest_digest("AI") is None

    def test_returns_most_recent(self, tmp_db, sample_news_items):
        run_id = save_run("2026-05-10", 1)
        save_report(run_id, "AI", "a1", "r1", 1.0, sample_news_items, digest="old digest")
        save_report(run_id, "AI", "a2", "r2", 1.0, sample_news_items, digest="new digest")
        assert get_latest_digest("AI") == "new digest"

    def test_filters_by_topic(self, tmp_db, sample_news_items):
        run_id = save_run("2026-05-10", 2)
        save_report(run_id, "AI", "a", "r", 1.0, sample_news_items, digest="ai digest")
        save_report(run_id, "Market", "a", "r", 1.0, sample_news_items, digest="market digest")
        assert get_latest_digest("AI") == "ai digest"
        assert get_latest_digest("Market") == "market digest"


class TestGetSeenFingerprints:
    def test_empty_when_no_rows(self, tmp_db):
        urls, hashes = get_seen_fingerprints(days=7)
        assert urls == set()
        assert hashes == set()

    def test_collects_urls_and_hashes(self, tmp_db, sample_news_items):
        run_id = save_run("2026-05-10", 1)
        save_report(run_id, "AI", "a", "r", 1.0, sample_news_items)
        urls, hashes = get_seen_fingerprints(days=7)
        assert "https://example.com/ai" in urls
        assert "https://news.com/market" in urls
        assert title_hash("AI Breakthrough") in hashes
        assert title_hash("Market Update") in hashes


class TestSaveReportPersistsDedupFields:
    def test_digest_persisted(self, tmp_db, sample_news_items):
        run_id = save_run("2026-05-10", 1)
        save_report(run_id, "AI", "a", "r", 1.0, sample_news_items, digest="abc")
        assert get_latest_digest("AI") == "abc"

    def test_title_hash_persisted(self, tmp_db, sample_news_items):
        from db import get_connection
        run_id = save_run("2026-05-10", 1)
        save_report(run_id, "AI", "a", "r", 1.0, sample_news_items)
        conn = get_connection()
        rows = conn.execute("SELECT title, title_hash FROM news_items").fetchall()
        conn.close()
        assert len(rows) == 2
        for row in rows:
            assert row["title_hash"] == title_hash(row["title"])
