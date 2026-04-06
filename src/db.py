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

CREATE TABLE IF NOT EXISTS feedback (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id        INTEGER REFERENCES reports(id) ON DELETE SET NULL,
    run_date         TEXT NOT NULL,
    topic            TEXT NOT NULL,
    rating           INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment          TEXT,
    email_message_id TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prompt_synthesis_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    synthesized_at  TEXT NOT NULL DEFAULT (datetime('now')),
    feedback_count  INTEGER NOT NULL,
    summary         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_topic    ON feedback(topic);
CREATE INDEX IF NOT EXISTS idx_feedback_run_date ON feedback(run_date);
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


def save_feedback(
    run_date: str,
    topic: str,
    rating: int,
    comment: str | None = None,
    email_message_id: str | None = None,
) -> int:
    """Insert a feedback record, auto-linking to the most recent report for (run_date, topic).
    Returns the new feedback row ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT r.id FROM reports r "
        "JOIN runs ru ON r.run_id = ru.id "
        "WHERE ru.run_date = ? AND r.topic = ? "
        "ORDER BY r.created_at DESC LIMIT 1",
        (run_date, topic),
    ).fetchone()
    report_id = row["id"] if row else None

    cursor = conn.execute(
        "INSERT INTO feedback (report_id, run_date, topic, rating, comment, email_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (report_id, run_date, topic, rating, comment, email_message_id),
    )
    conn.commit()
    fid = cursor.lastrowid
    conn.close()
    return fid


def get_feedback_ratings(report_ids: list[int]) -> dict[int, int]:
    """Return {report_id: rating} for a list of report IDs. Used by RAG to filter by quality."""
    if not report_ids:
        return {}
    conn = get_connection()
    placeholders = ",".join("?" * len(report_ids))
    rows = conn.execute(
        f"SELECT report_id, MAX(rating) as rating FROM feedback "
        f"WHERE report_id IN ({placeholders}) AND report_id IS NOT NULL "
        f"GROUP BY report_id",
        report_ids,
    ).fetchall()
    conn.close()
    return {row["report_id"]: row["rating"] for row in rows}


def get_recent_feedback(limit: int = 20) -> list[dict]:
    """Return the most recent feedback items with non-empty comments, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT topic, rating, comment, run_date, created_at "
        "FROM feedback "
        "WHERE comment IS NOT NULL AND comment != '' "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def count_feedback_since_last_synthesis() -> int:
    """Return number of feedback rows created since the last prompt synthesis run."""
    conn = get_connection()
    last = conn.execute(
        "SELECT synthesized_at FROM prompt_synthesis_log ORDER BY synthesized_at DESC LIMIT 1"
    ).fetchone()
    if last is None:
        count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE created_at > ?",
            (last["synthesized_at"],),
        ).fetchone()[0]
    conn.close()
    return count


def save_synthesis_log(feedback_count: int, summary: str) -> None:
    """Record a completed prompt synthesis run."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO prompt_synthesis_log (feedback_count, summary) VALUES (?, ?)",
        (feedback_count, summary),
    )
    conn.commit()
    conn.close()
