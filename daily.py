"""Daily runner: analyze all topics and send combined report via email."""

import json
import time
from datetime import date

from graph import graph
from notifier import send_email


def run_daily():
    with open("config.json") as f:
        config = json.load(f)

    topics = config["topics"]
    to_address = config["email"]["to"]
    today = date.today().isoformat()

    reports = []
    for topic in topics:
        print(f"Analyzing: {topic}")
        state = {
            "messages": [],
            "topic": topic,
            "news_items": [],
            "analysis": "",
            "conflicts": [],
            "iterations": 0,
            "final_report": "",
        }
        start = time.time()
        result = graph.invoke(state)
        elapsed = time.time() - start

        reports.append(
            f"{'=' * 60}\n"
            f"Topic: {topic}\n"
            f"{'=' * 60}\n\n"
            f"{result['final_report']}\n\n"
            f"(Completed in {elapsed:.1f}s)\n"
        )
        print(f"  Done in {elapsed:.1f}s")

    body = f"Daily News Analysis Report — {today}\n\n" + "\n".join(reports)
    subject = f"Daily News Report — {today}"

    send_email(subject, body, to_address)
    print(f"\nAll {len(topics)} topics analyzed and emailed.")


if __name__ == "__main__":
    run_daily()
