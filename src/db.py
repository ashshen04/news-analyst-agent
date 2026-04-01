"""SQLite database layer for storing news analysis reports."""

import os
import sqlite3
from pathlib import Path

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date     TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    topics_count INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES runs(id),
    topic        TEXT NOT NULL,
    analysis     TEXT,
    final_report TEXT NOT NULL,
    elapsed      REAL NOT NULL,
    news_count   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS news_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id    INTEGER NOT NULL REFERENCES reports(id),
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    source       TEXT NOT NULL,
    content      TEXT,
    fetched_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reports_topic ON reports(topic);
CREATE INDEX IF NOT EXISTS idx_reports_run ON reports(run_id);
CREATE INDEX IF NOT EXISTS idx_news_report ON news_items(report_id);
"""


def get_db_path() -> str:
    """Return DB path: /tmp/ on Lambda, ./data/ locally."""
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/news_analyst.db"
    path = Path("data/news_analyst.db")
    path.parent.mkdir(exist_ok=True)
    return str(path)


def get_connection() -> sqlite3.Connection:
    """Open a connection and ensure tables exist."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_CREATE_TABLES)
    return conn


def save_run(run_date: str, topics_count: int, status: str = "success") -> int:
    """Insert a run record and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO runs (run_date, topics_count, status) VALUES (?, ?, ?)",
        (run_date, topics_count, status),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()
    return run_id


def update_run_status(run_id: int, status: str) -> None:
    """Update the status of an existing run."""
    conn = get_connection()
    conn.execute("UPDATE runs SET status = ? WHERE id = ?", (status, run_id))
    conn.commit()
    conn.close()


def save_report(
    run_id: int,
    topic: str,
    analysis: str,
    final_report: str,
    elapsed: float,
    news_items: list[dict],
) -> int:
    """Insert a report and its news items. Returns report ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO reports (run_id, topic, analysis, final_report, elapsed, news_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, topic, analysis, final_report, elapsed, len(news_items)),
    )
    report_id = cursor.lastrowid

    for item in news_items:
        conn.execute(
            "INSERT INTO news_items (report_id, title, url, source, content) "
            "VALUES (?, ?, ?, ?, ?)",
            (report_id, item.get("title", ""), item.get("url", ""),
             item.get("source", ""), item.get("content", "")),
        )

    conn.commit()
    conn.close()
    return report_id


def get_recent_reports(topic: str, limit: int = 7) -> list[dict]:
    """Get recent reports for a topic, ordered by newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT r.*, ru.run_date FROM reports r "
        "JOIN runs ru ON r.run_id = ru.id "
        "WHERE r.topic = ? ORDER BY r.created_at DESC LIMIT ?",
        (topic, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_run_history(limit: int = 30) -> list[dict]:
    """Get recent runs, ordered by newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
