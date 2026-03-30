"""AWS Lambda handler for daily news analysis reports."""

import json

from daily import run_daily


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    result = run_daily()
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": f"Report sent for {result['topics']} topics",
            "date": result["date"],
        }),
    }
