"""AgentState definition for the news analyst agent."""

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State schema for the news analyst agent graph."""

    messages: Annotated[list, add_messages]
    topic: str
    news_items: list[dict]
    analysis: str
    conflicts: list[str]
    iterations: int
    final_report: str
