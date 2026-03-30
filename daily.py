"""Daily runner: analyze all topics and send combined report via email."""

import json
import time
from datetime import date

from graph import graph
from nodes import llm
from notifier import send_email
from template import build_report_html


def run_daily():
    """Core logic: analyze all topics and send email report. Returns summary dict."""
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

        reports.append({
            "topic": topic,
            "final_report": result["final_report"],
            "elapsed": elapsed,
        })
        print(f"  Done in {elapsed:.1f}s")

    html_body = build_report_html(today, reports, model=llm.model_name)
    subject = f"Daily News Report — {today}"

    send_email(subject, html_body, to_address)
    print(f"\nAll {len(topics)} topics analyzed and emailed.")

    return {"topics": len(topics), "date": today}


if __name__ == "__main__":
    run_daily()
