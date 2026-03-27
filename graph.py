"""LangGraph workflow definition for the news analyst agent."""

from langgraph.graph import END, StateGraph

from nodes import analyze_news, fetch_news, find_conflicts, generate_report
from state import AgentState


def should_retry(state: AgentState) -> str:
    """Decide whether to retry fetching or proceed to report generation."""
    if state["iterations"] < 2 and not state["conflicts"]:
        return "fetch_news"
    return "generate_report"


builder = StateGraph(AgentState)

builder.add_node("fetch_news", fetch_news)
builder.add_node("analyze_news", analyze_news)
builder.add_node("find_conflicts", find_conflicts)
builder.add_node("generate_report", generate_report)

builder.set_entry_point("fetch_news")
builder.add_edge("fetch_news", "analyze_news")
builder.add_edge("analyze_news", "find_conflicts")
builder.add_conditional_edges("find_conflicts", should_retry)
builder.add_edge("generate_report", END)

graph = builder.compile()
