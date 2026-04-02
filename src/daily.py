"""Daily runner: analyze all topics and send combined report via email."""

import json
import logging
import os
import time
from datetime import date

import boto3

from db import save_report, save_run, update_run_status
from graph import graph
from logger import setup_logging
from nodes import llm
from notifier import send_email
from template import build_report_html

logger = logging.getLogger(__name__)


def archive_to_s3(today: str, reports: list, failed_topics: list) -> None:
    """Save run results to S3 as reports/YYYY-MM-DD.json. Only runs on Lambda."""
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        return
    record = {
        "date": today,
        "reports": [
            {
                "topic": r["topic"],
                "final_report": r["final_report"],
                "news_items": r["news_items"],
                "elapsed": r["elapsed"],
            }
            for r in reports
        ],
        "failed_topics": failed_topics,
    }
    boto3.client("s3").put_object(
        Bucket=bucket,
        Key=f"reports/{today}.json",
        Body=json.dumps(record, ensure_ascii=False),
        ContentType="application/json",
    )
    logger.info("Archived to s3://%s/reports/%s.json", bucket, today)


def run_daily():
    """Core logic: analyze all topics and send email report. Returns summary dict."""
    setup_logging()

    with open("config.json") as f:
        config = json.load(f)

    topics = config["topics"]
    to_address = config["email"]["to"]
    today = date.today().isoformat()

    run_id = save_run(today, len(topics))
    failed_topics = []

    reports = []
    for topic in topics:
        logger.info("Analyzing: %s", topic)
        state = {
            "messages": [],
            "topic": topic,
            "news_items": [],
            "analysis": "",
            "conflicts": [],
            "iterations": 0,
            "final_report": "",
        }
        try:
            start = time.time()
            result = graph.invoke(state)
            elapsed = time.time() - start

            reports.append({
                "topic": topic,
                "final_report": result["final_report"],
                "analysis": result["analysis"],
                "news_items": result["news_items"],
                "elapsed": elapsed,
            })

            save_report(
                run_id=run_id,
                topic=topic,
                analysis=result["analysis"],
                final_report=result["final_report"],
                elapsed=elapsed,
                news_items=result["news_items"],
            )
            logger.info("Done: %s in %.1fs", topic, elapsed)

        except Exception:
            logger.exception("Failed to analyze topic: %s", topic)
            failed_topics.append(topic)

    if failed_topics:
        update_run_status(run_id, "partial" if reports else "failed")

    if reports:
        html_body = build_report_html(today, reports, model=llm.model_name)
        subject = f"Daily News Report — {today}"
        if failed_topics:
            subject += f" ({len(failed_topics)} topic(s) failed)"
        send_email(subject, html_body, to_address)

    archive_to_s3(today, reports, failed_topics)

    if failed_topics:
        logger.error("Failed topics: %s", ", ".join(failed_topics))

    logger.info("Run complete: %d/%d topics succeeded", len(reports), len(topics))
    return {"topics": len(reports), "failed": len(failed_topics), "date": today}


if __name__ == "__main__":
    run_daily()
