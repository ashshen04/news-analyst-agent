"""Node definitions for the news analyst agent graph."""

import logging
import os
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from groq import InternalServerError, RateLimitError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)

from db import get_latest_digest, get_seen_fingerprints, title_hash
from state import AgentState
from tools import search_news

load_dotenv()

_PREFS_PATH = Path(__file__).parent / "user_preferences.md"


def _load_system_prompt() -> str:
    base = Path(__file__).parent.joinpath("system_prompt.md").read_text()
    if _PREFS_PATH.exists():
        prefs = _PREFS_PATH.read_text().strip()
        if prefs:
            return base + "\n\n# User Preferences\n" + prefs
    return base


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
)


def invoke_with_retry(prompt: str, max_retries: int = 3, wait: float = 10.0) -> str:
    """Invoke the LLM with system prompt and retry on errors."""
    messages = [SystemMessage(content=_load_system_prompt()), HumanMessage(content=prompt)]
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            return response.content
        except (RateLimitError, InternalServerError) as e:
            if attempt < max_retries - 1:
                logger.warning("LLM error on attempt %d/%d: %s. Retrying in %.0fs...", attempt + 1, max_retries, e, wait)
                time.sleep(wait)
            else:
                logger.error("LLM failed after %d attempts", max_retries)
                raise
    return ""


def fetch_news(state: AgentState) -> dict:
    """Fetch news articles for the given topic, dropping ones we've already analyzed recently."""
    logger.info("Fetching news for: %s", state["topic"])
    results = search_news(state["topic"])
    raw_count = len(results)

    try:
        seen_urls, seen_hashes = get_seen_fingerprints(days=7)
        results = [
            item for item in results
            if item.get("url") not in seen_urls
            and title_hash(item.get("title", "")) not in seen_hashes
        ]
    except Exception:
        logger.exception("Dedup lookup failed — proceeding with unfiltered results")

    logger.info("Fetched %d articles (%d after dedup)", raw_count, len(results))
    return {
        "news_items": results,
        "iterations": state["iterations"] + 1,
    }


def analyze_news(state: AgentState) -> dict:
    """Analyze fetched news to identify stances and key viewpoints."""
    news_text = "\n\n".join(
        f"[{item['source']}] {item['title']}\n{item['content']}"
        for item in state["news_items"]
    )
    result = invoke_with_retry(
        f"Below are news articles about \"{state['topic']}\".\n\n"
        f"{news_text}\n\n"
        "Analyze these articles. Identify the different stances, "
        "key viewpoints, and major themes across sources."
    )
    return {"analysis": result}


def find_conflicts(state: AgentState) -> dict:
    """Identify contradictions between different sources."""
    result = invoke_with_retry(
        f"Below is an analysis of news articles about \"{state['topic']}\":\n\n"
        f"{state['analysis']}\n\n"
        "Identify specific contradictions or conflicting claims between "
        "different sources. Return each contradiction as a separate item. "
        "Be concise — one sentence per contradiction."
    )
    conflicts = [
        line.lstrip("•-0123456789. ")
        for line in result.strip().splitlines()
        if line.strip()
    ]
    return {"conflicts": conflicts}


def generate_report(state: AgentState) -> dict:
    """Generate a structured final report."""
    conflicts_text = "\n".join(f"- {c}" for c in state["conflicts"])

    prior_block = ""
    try:
        prior = get_latest_digest(state["topic"])
    except Exception:
        logger.exception("Prior digest lookup failed — proceeding without memory")
        prior = None
    if prior:
        prior_block = (
            f"<previous_day_digest>\n{prior}\n</previous_day_digest>\n\n"
            "The above is the digest of the most recent prior report on this topic. "
            "Focus your report on what is NEW today; do not restate points already covered. "
            "If today's news confirms or contradicts the prior digest, say so explicitly.\n\n"
        )

    result = invoke_with_retry(
        f"{prior_block}"
        f"Topic: {state['topic']}\n\n"
        f"Analysis:\n{state['analysis']}\n\n"
        f"Contradictions found:\n{conflicts_text}\n\n"
        f"Today's date: {date.today().isoformat()}\n\n"
        "Based on the above, generate a structured report with these sections:\n"
        "1. Executive Summary\n"
        "2. Key Findings\n"
        "3. Conflicting Information\n"
        "4. Conclusion\n\n"
        "Include the report date and note the recency of the news sources."
    )
    return {"final_report": result}


def summarize_for_memory(state: AgentState) -> dict:
    """Compress today's final report into a ~100-word digest for tomorrow's run."""
    if not state.get("final_report"):
        return {"digest": ""}
    result = invoke_with_retry(
        "Compress the following report into a digest of at most 100 words for use as memory "
        "tomorrow. Keep only: key entities, decisions, claims, numbers, and unresolved "
        "questions. No headings, no flowery prose, no restatement of the topic. Plain prose, "
        "one paragraph.\n\n"
        f"{state['final_report']}"
    )
    return {"digest": result.strip()}
