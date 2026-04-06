"""Synthesize user preferences from feedback comments and update user_preferences.md."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from db import count_feedback_since_last_synthesis, get_recent_feedback, save_synthesis_log

logger = logging.getLogger(__name__)

load_dotenv()

PREFS_PATH = Path(__file__).parent / "user_preferences.md"
SYNTHESIS_THRESHOLD = 3

_SYNTHESIS_SYSTEM_PROMPT = """\
You are an AI assistant that helps improve a news analysis report generator.
You will be given a list of user feedback items (ratings and comments) about past reports.
Your job is to synthesize actionable writing instructions from the feedback patterns.
Output ONLY a markdown bullet list of concrete instructions, each starting with a verb.
Do not summarize the feedback — turn it into rules the report generator should follow.
Keep it under 200 words. Write in English."""

_SYNTHESIS_USER_TEMPLATE = """\
Here are recent user feedback items for the news analysis reports:

{feedback_block}

Based on the patterns above, write a concise bullet list of instructions to guide future report generation.
Focus on style, structure, tone, depth, and format preferences that appear consistently."""


def should_evolve_prompt() -> bool:
    """Return True if enough new feedback has arrived to warrant a synthesis run."""
    count = count_feedback_since_last_synthesis()
    logger.info("New feedback since last synthesis: %d (threshold: %d)", count, SYNTHESIS_THRESHOLD)
    return count >= SYNTHESIS_THRESHOLD


def evolve_prompt() -> bool:
    """Synthesize user preferences from recent feedback and write user_preferences.md.

    Returns True if synthesis ran successfully, False if skipped or failed.
    """
    if not should_evolve_prompt():
        logger.info("Skipping prompt evolution — not enough new feedback")
        return False

    feedback_items = get_recent_feedback(limit=20)
    if not feedback_items:
        return False

    feedback_block = "\n\n".join(
        f"- Topic: {f['topic']}, Rating: {f['rating']}/5, Date: {f['run_date']}\n"
        f"  Comment: {f['comment']}"
        for f in feedback_items
    )

    prompt = _SYNTHESIS_USER_TEMPLATE.format(feedback_block=feedback_block)

    try:
        llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=os.environ["GROQ_API_KEY"],
        )
        response = llm.invoke([
            SystemMessage(content=_SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        instructions = response.content.strip()
    except Exception:
        logger.exception("LLM synthesis call failed — user_preferences.md not updated")
        return False

    PREFS_PATH.write_text(instructions, encoding="utf-8")
    save_synthesis_log(feedback_count=len(feedback_items), summary=instructions[:500])
    logger.info("user_preferences.md updated (%d chars)", len(instructions))
    return True
