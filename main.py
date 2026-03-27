"""Entry point for the news analyst agent."""

import sys
import time

from graph import graph


def main():
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = input("🧐 Enter a news topic to analyze: ").strip()

    if not topic:
        print("No topic provided. Exiting.")
        sys.exit(1)

    state = {
        "messages": [],
        "topic": topic,
        "news_items": [],
        "analysis": "",
        "conflicts": [],
        "iterations": 0,
        "final_report": "",
    }

    print(f"Analyzing: {topic}\n")
    start = time.time()
    result = graph.invoke(state)
    elapsed = time.time() - start

    print(result["final_report"])
    print(f"\n--- Completed in {elapsed:.1f}s ---")


if __name__ == "__main__":
    main()
