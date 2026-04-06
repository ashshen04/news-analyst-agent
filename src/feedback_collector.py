"""Poll Gmail IMAP for feedback replies to daily report emails."""

import email
import imaplib
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from email.header import decode_header

from dotenv import load_dotenv

from db import save_feedback

logger = logging.getLogger(__name__)

load_dotenv()

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

_SUBJECT_RE = re.compile(
    r"Re:\s*Daily News Report\s*[—\-]\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)
_RATING_RE = re.compile(r"rating\s*[:\-]?\s*([1-5])(?:\s*/\s*5)?", re.IGNORECASE)
_TOPIC_RE = re.compile(r"topic\s*[:\-]\s*(.+)", re.IGNORECASE)
_COMMENT_RE = re.compile(r"comment\s*[:\-]\s*(.+)", re.IGNORECASE | re.DOTALL)


@dataclass
class ParsedFeedback:
    run_date: str
    topic: str
    rating: int
    comment: str | None
    message_id: str | None


def collect_feedback(known_topics: list[str], lookback_days: int = 7) -> int:
    """Poll IMAP for reply emails and persist feedback to DB.

    Args:
        known_topics: Active topic names used for fuzzy matching.
        lookback_days: How many days back to search for replies.

    Returns:
        Number of new feedback items saved.
    """
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_address or not gmail_password:
        logger.warning("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping feedback collection")
        return 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(gmail_address, gmail_password)
        mail.select("INBOX")
    except Exception:
        logger.exception("IMAP connection/login failed — skipping feedback collection")
        return 0

    since_date = (date.today() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
    _, data = mail.search(None, f'(SINCE "{since_date}" SUBJECT "Re: Daily News Report")')

    message_nums = data[0].split()
    logger.info("IMAP: found %d candidate reply email(s)", len(message_nums))

    seen_ids = _get_seen_message_ids()
    saved = 0

    for num in message_nums:
        try:
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            message_id = msg.get("Message-ID", "").strip()
            if message_id and message_id in seen_ids:
                logger.debug("Skipping already-processed message: %s", message_id)
                continue

            parsed = _parse_email(msg, known_topics)
            if parsed is None:
                logger.debug("Could not parse feedback from message %s", message_id)
                continue

            save_feedback(
                run_date=parsed.run_date,
                topic=parsed.topic,
                rating=parsed.rating,
                comment=parsed.comment,
                email_message_id=parsed.message_id,
            )
            seen_ids.add(message_id)
            saved += 1
            logger.info(
                "Saved feedback: topic=%s rating=%d date=%s",
                parsed.topic, parsed.rating, parsed.run_date,
            )
        except Exception:
            logger.exception("Error processing email #%s", num)

    mail.logout()
    logger.info("Feedback collection complete: %d new item(s) saved", saved)
    return saved


def _get_seen_message_ids() -> set[str]:
    """Load Message-IDs already in DB to prevent duplicates."""
    from db import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT email_message_id FROM feedback WHERE email_message_id IS NOT NULL"
    ).fetchall()
    conn.close()
    return {row["email_message_id"] for row in rows}


def _parse_email(msg, known_topics: list[str]) -> ParsedFeedback | None:
    """Extract run_date, topic, rating, comment from a reply email."""
    subject = _decode_header_value(msg.get("Subject", ""))
    match = _SUBJECT_RE.search(subject)
    if not match:
        return None
    run_date = match.group(1)

    body = _extract_body(msg)
    if not body:
        return None

    r_match = _RATING_RE.search(body)
    if not r_match:
        return None
    rating = int(r_match.group(1))

    topic = _match_topic(body, known_topics)
    if topic is None:
        return None

    c_match = _COMMENT_RE.search(body)
    if c_match:
        comment = c_match.group(1).strip()
        comment = comment.splitlines()[0].strip() if comment else None
    else:
        comment = _extract_freeform_comment(body)

    message_id = msg.get("Message-ID", "").strip() or None

    return ParsedFeedback(
        run_date=run_date,
        topic=topic,
        rating=rating,
        comment=comment or None,
        message_id=message_id,
    )


def _extract_body(msg) -> str:
    """Get plain text from email, stripping quoted reply lines (starting with >)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")

    lines = [line for line in body.splitlines() if not line.startswith(">")]
    return "\n".join(lines).strip()


def _match_topic(body: str, known_topics: list[str]) -> str | None:
    """Find topic from structured 'Topic: ...' field or by substring match."""
    t_match = _TOPIC_RE.search(body)
    if t_match:
        candidate = t_match.group(1).strip().splitlines()[0].strip()
        for topic in known_topics:
            if topic.lower() in candidate.lower() or candidate.lower() in topic.lower():
                return topic
        return candidate

    for topic in known_topics:
        if topic.lower() in body.lower():
            return topic
    return None


def _decode_header_value(raw: str) -> str:
    parts = decode_header(raw)
    out = []
    for fragment, enc in parts:
        if isinstance(fragment, bytes):
            out.append(fragment.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(fragment)
    return "".join(out)


def _extract_freeform_comment(body: str) -> str | None:
    """Extract non-structured lines as a freeform comment."""
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not _RATING_RE.match(stripped) and not _TOPIC_RE.match(stripped):
            lines.append(stripped)
    return " ".join(lines) if lines else None
