"""Tool definitions for the news analyst agent."""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))


def search_news(topic: str, max_results: int = 5) -> list[dict]:
    """Search for news articles on a given topic using Tavily."""
    try:
        response = client.search(
            query=topic,
            search_depth="advanced",
            topic="news",
            max_results=max_results,
        )
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "source": urlparse(item.get("url", "")).netloc,
            }
            for item in response.get("results", [])
        ]
    except Exception:
        return []
