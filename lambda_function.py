"""AWS Lambda handler for daily news analysis reports."""

import json
import time
from datetime import date

from graph import graph
from notifier import send_email
from template import build_report_html


def lambda_handler(event, context):
    """AWS Lambda entry point."""
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

    html_body = build_report_html(today, reports)
    subject = f"Daily News Report — {today}"

    send_email(subject, html_body, to_address)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Report sent for {len(topics)} topics",
            "date": today,
        }),
    }
