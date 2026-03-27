"""Email notification for daily news reports."""

import os
import smtplib
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()


def send_email(subject: str, body: str, to_addresses: str | list[str]) -> None:
    """Send an email via Gmail SMTP. Accepts a single address or a list."""
    gmail_address = os.getenv("GMAIL_ADDRESS")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = ", ".join(to_addresses)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_password)
        server.send_message(msg)

    print(f"Email sent to {', '.join(to_addresses)}")
