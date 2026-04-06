"""RAG module: embed reports with fastembed and retrieve similar examples via FAISS."""

import json
import logging
import os
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

_embedder: TextEmbedding | None = None


def _get_embedder() -> TextEmbedding:
    global _embedder
    if _embedder is None:
        logger.info("Loading fastembed model: %s", MODEL_NAME)
        _embedder = TextEmbedding(MODEL_NAME)
    return _embedder


def _get_faiss_path() -> str:
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/report_vectors.faiss"
    Path("data").mkdir(exist_ok=True)
    return "data/report_vectors.faiss"


def _get_meta_path() -> str:
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/report_vectors_meta.json"
    Path("data").mkdir(exist_ok=True)
    return "data/report_vectors_meta.json"


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns a normalized float32 vector."""
    embedder = _get_embedder()
    vectors = list(embedder.embed([text[:4096]]))
    vec = np.array(vectors[0], dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def add_report(report_id: int, topic: str, run_date: str, text: str) -> None:
    """Embed a report and add it to the FAISS index."""
    faiss_path = _get_faiss_path()
    meta_path = _get_meta_path()

    vec = embed_text(text)
    dim = vec.shape[0]

    if Path(faiss_path).exists():
        index = faiss.read_index(faiss_path)
        with open(meta_path) as f:
            meta = json.load(f)
    else:
        index = faiss.IndexFlatIP(dim)
        meta = []

    index.add(vec.reshape(1, -1))
    meta.append({"report_id": report_id, "topic": topic, "run_date": run_date})

    faiss.write_index(index, faiss_path)
    with open(meta_path, "w") as f:
        json.dump(meta, f)

    logger.info("Indexed report_id=%d (topic=%s) — index size: %d", report_id, topic, index.ntotal)


def retrieve_examples(
    query_text: str,
    top_k: int = 2,
    min_rating: int = 4,
) -> list[dict]:
    """Retrieve semantically similar high-rated past reports for use as few-shot examples.

    Args:
        query_text: The current analysis text used as the search query.
        top_k: Max number of examples to return.
        min_rating: Minimum feedback rating to include (1-5).

    Returns:
        List of dicts with keys: final_report, topic, rating, run_date.
        Empty list if index doesn't exist or no qualifying examples found.
    """
    faiss_path = _get_faiss_path()
    meta_path = _get_meta_path()

    if not Path(faiss_path).exists():
        logger.debug("FAISS index not found — skipping RAG retrieval")
        return []

    from db import get_feedback_ratings, get_recent_reports

    index = faiss.read_index(faiss_path)
    with open(meta_path) as f:
        meta = json.load(f)

    if index.ntotal == 0:
        return []

    query_vec = embed_text(query_text).reshape(1, -1)
    search_k = min(20, index.ntotal)
    _, indices = index.search(query_vec, search_k)

    candidate_report_ids = [
        meta[i]["report_id"]
        for i in indices[0]
        if i >= 0 and i < len(meta)
    ]

    if not candidate_report_ids:
        return []

    ratings = get_feedback_ratings(candidate_report_ids)

    results = []
    seen_ids = set()
    for i in indices[0]:
        if i < 0 or i >= len(meta):
            continue
        entry = meta[i]
        rid = entry["report_id"]
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        rating = ratings.get(rid)
        if rating is None or rating < min_rating:
            continue

        reports = get_recent_reports(entry["topic"], limit=30)
        report_row = next((r for r in reports if r["id"] == rid), None)
        if report_row is None:
            continue

        results.append({
            "final_report": report_row["final_report"][:3000],
            "topic": entry["topic"],
            "rating": rating,
            "run_date": entry["run_date"],
        })

        if len(results) >= top_k:
            break

    logger.info("RAG retrieved %d example(s) for query (min_rating=%d)", len(results), min_rating)
    return results
