"""Shared fixtures for all tests — mocks external APIs so no real calls are made."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the src/ directory is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------------------------------------------------------------------------
# Fake environment so modules can import without real keys
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _fake_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-groq-key")
    monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "fake-password")


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------
SAMPLE_NEWS_ITEMS = [
    {
        "title": "AI Breakthrough",
        "url": "https://example.com/ai",
        "content": "New AI model released.",
        "source": "example.com",
    },
    {
        "title": "Market Update",
        "url": "https://news.com/market",
        "content": "Stocks rose sharply today.",
        "source": "news.com",
    },
]


@pytest.fixture
def sample_news_items():
    return SAMPLE_NEWS_ITEMS.copy()


@pytest.fixture
def sample_state(sample_news_items):
    return {
        "messages": [],
        "topic": "AI Latest News",
        "news_items": sample_news_items,
        "analysis": "Both sources agree AI is advancing rapidly.",
        "conflicts": ["Source A says costs decrease, Source B says costs increase."],
        "iterations": 1,
        "final_report": "",
    }


# ---------------------------------------------------------------------------
# Temp SQLite database
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point db.get_db_path() to a temp database."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("db.get_db_path", lambda: db_path)
    return db_path
