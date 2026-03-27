"""Node definitions for the news analyst agent graph."""

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from state import AgentState
from tools import search_news

load_dotenv()

llm = ChatGroq(
    model="qwen/qwen3-32b",
    api_key=os.getenv("GROQ_API_KEY"),
)


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
    response = llm.invoke(
        f"Below are news articles about \"{state['topic']}\".\n\n"
        f"{news_text}\n\n"
        "Analyze these articles. Identify the different stances, "
        "key viewpoints, and major themes across sources."
    )
    return {"analysis": response.content}


def find_conflicts(state: AgentState) -> dict:
    """Identify contradictions between different sources."""
    response = llm.invoke(
        f"Below is an analysis of news articles about \"{state['topic']}\":\n\n"
        f"{state['analysis']}\n\n"
        "Identify specific contradictions or conflicting claims between "
        "different sources. Return each contradiction as a separate item. "
        "Be concise — one sentence per contradiction."
    )
    conflicts = [
        line.lstrip("•-0123456789. ")
        for line in response.content.strip().splitlines()
        if line.strip()
    ]
    return {"conflicts": conflicts}


def generate_report(state: AgentState) -> dict:
    """Generate a structured final report."""
    conflicts_text = "\n".join(f"- {c}" for c in state["conflicts"])
    response = llm.invoke(
        f"Topic: {state['topic']}\n\n"
        f"Analysis:\n{state['analysis']}\n\n"
        f"Contradictions found:\n{conflicts_text}\n\n"
        "Based on the above, generate a structured report with these sections:\n"
        "1. Executive Summary\n"
        "2. Key Findings\n"
        "3. Conflicting Information\n"
        "4. Conclusion"
    )
    return {"final_report": response.content}
