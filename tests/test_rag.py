"""Tests for rag.py — FAISS index and retrieval with mocked embeddings."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture
def mock_embedder(monkeypatch):
    """Replace fastembed TextEmbedding with a mock that returns fixed 4-dim vectors."""
    fake = MagicMock()
    fake.embed.side_effect = lambda texts: [np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)]
    monkeypatch.setattr("rag._embedder", fake)
    return fake


@pytest.fixture
def rag_paths(tmp_path, monkeypatch):
    """Redirect FAISS and meta paths to tmp_path."""
    faiss_path = str(tmp_path / "test.faiss")
    meta_path = str(tmp_path / "test_meta.json")
    monkeypatch.setattr("rag._get_faiss_path", lambda: faiss_path)
    monkeypatch.setattr("rag._get_meta_path", lambda: meta_path)
    return faiss_path, meta_path


class TestEmbedText:
    def test_returns_normalized_float32(self, mock_embedder):
        from rag import embed_text
        vec = embed_text("hello world")
        assert vec.dtype == np.float32
        assert abs(np.linalg.norm(vec) - 1.0) < 1e-5


class TestAddReport:
    def test_creates_index_on_first_add(self, mock_embedder, rag_paths):
        import os
        from rag import add_report
        faiss_path, meta_path = rag_paths
        add_report(report_id=1, topic="AI", run_date="2026-04-04", text="Report text")
        assert os.path.exists(faiss_path)
        assert os.path.exists(meta_path)

    def test_meta_contains_correct_fields(self, mock_embedder, rag_paths):
        from rag import add_report
        _, meta_path = rag_paths
        add_report(report_id=42, topic="Finance", run_date="2026-04-04", text="Report")
        with open(meta_path) as f:
            meta = json.load(f)
        assert len(meta) == 1
        assert meta[0]["report_id"] == 42
        assert meta[0]["topic"] == "Finance"
        assert meta[0]["run_date"] == "2026-04-04"

    def test_appends_multiple_reports(self, mock_embedder, rag_paths):
        import faiss
        from rag import add_report
        faiss_path, meta_path = rag_paths
        add_report(1, "AI", "2026-04-04", "Report 1")
        add_report(2, "Finance", "2026-04-05", "Report 2")
        index = faiss.read_index(faiss_path)
        assert index.ntotal == 2
        with open(meta_path) as f:
            meta = json.load(f)
        assert len(meta) == 2


class TestRetrieveExamples:
    def test_returns_empty_when_no_index(self, mock_embedder, rag_paths, tmp_db):
        from rag import retrieve_examples
        results = retrieve_examples("query text")
        assert results == []

    def test_returns_empty_when_no_high_rated_reports(self, mock_embedder, rag_paths, tmp_db):
        from db import save_feedback, save_report, save_run
        from rag import add_report, retrieve_examples

        run_id = save_run("2026-04-04", 1)
        report_id = save_report(run_id, "AI", "a", "final report text", 1.0, [])
        add_report(report_id, "AI", "2026-04-04", "final report text")
        save_feedback("2026-04-04", "AI", 3, "Just okay")

        results = retrieve_examples("some query", min_rating=4)
        assert results == []

    def test_returns_high_rated_report(self, mock_embedder, rag_paths, tmp_db):
        from db import save_feedback, save_report, save_run
        from rag import add_report, retrieve_examples

        run_id = save_run("2026-04-04", 1)
        report_id = save_report(run_id, "AI", "a", "Great report content", 1.0, [])
        add_report(report_id, "AI", "2026-04-04", "Great report content")
        save_feedback("2026-04-04", "AI", 5, "Excellent")

        results = retrieve_examples("some query about AI", min_rating=4)
        assert len(results) == 1
        assert results[0]["rating"] == 5
        assert results[0]["topic"] == "AI"

    def test_respects_top_k(self, mock_embedder, rag_paths, tmp_db):
        from db import save_feedback, save_report, save_run
        from rag import add_report, retrieve_examples

        run_id = save_run("2026-04-04", 2)
        for i in range(3):
            report_id = save_report(run_id, f"Topic{i}", "a", f"Report {i}", 1.0, [])
            add_report(report_id, f"Topic{i}", "2026-04-04", f"Report {i}")
            save_feedback("2026-04-04", f"Topic{i}", 5, f"Comment {i}")

        results = retrieve_examples("query", top_k=2, min_rating=4)
        assert len(results) <= 2
