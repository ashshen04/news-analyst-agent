"""Node definitions for the news analyst agent graph."""

import os
from datetime import date

from dotenv import load_dotenv
from groq import RateLimitError
from langchain_groq import ChatGroq

from state import AgentState
from tools import search_news

load_dotenv()

llm = ChatGroq(
    model="moonshotai/kimi-k2-instruct",
    api_key=os.getenv("GROQ_API_KEY"),
)


def invoke_with_retry(prompt: str, max_retries: int = 3, wait: float = 10.0) -> str:
    """Invoke the LLM with retry on rate limit errors."""
    for attempt in range(max_retries):
        try:
            response = llm.invoke(prompt)
            return response.content
        except RateLimitError:
            if attempt < max_retries - 1:
                print(f"  Rate limited, waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                raise
    return ""


def fetch_news(state: AgentState) -> dict:
    """Fetch news articles for the given topic."""
    results = search_news(state["topic"])
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
        "key viewpoints, and major themes across sources.\n\n"
        "Respond in both English and Simplified Chinese (English first, then Chinese).\n"
        "Use bullet points for stances and viewpoints. Use short paragraphs only for context."
    )
    return {"analysis": result}


def find_conflicts(state: AgentState) -> dict:
    """Identify contradictions between different sources."""
    result = invoke_with_retry(
        f"Below is an analysis of news articles about \"{state['topic']}\":\n\n"
        f"{state['analysis']}\n\n"
        "Identify specific contradictions or conflicting claims between "
        "different sources. Return each contradiction as a separate item. "
        "Be concise — one sentence per contradiction.\n\n"
        "Respond in both English and Simplified Chinese (English first, then Chinese)."
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
    result = invoke_with_retry(
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
