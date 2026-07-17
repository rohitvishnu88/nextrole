"""Freshness verification for job postings: closure detection and re-verify cadence."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import re
import httpx

REVERIFY_INTERVAL = timedelta(hours=24)

CLOSURE_PHRASES = (
    "no longer accepting applications",
    "this position has been filled",
    "this job posting is no longer active",
    "position is no longer available",
)


def looks_closed(page_text: str) -> bool:
    lowered = page_text.lower()
    return any(phrase in lowered for phrase in CLOSURE_PHRASES)


def needs_reverify(last_verified_at_iso: str, now: datetime) -> bool:
    """`now` must be timezone-aware (UTC), per this codebase's convention.

    `last_verified_at_iso` is normalised to UTC if it was stored as a naive
    timestamp, so a legacy naive record doesn't blow up the comparison.
    """
    if not last_verified_at_iso:
        return True
    last_verified = datetime.fromisoformat(last_verified_at_iso)
    if last_verified.tzinfo is None:
        last_verified = last_verified.replace(tzinfo=timezone.utc)
    return now - last_verified >= REVERIFY_INTERVAL


def parse_greenhouse(url: str):
    parsed = urlparse(url)
    if parsed.netloc.lower() != "boards.greenhouse.io":
        return None
    match = re.search(r"^/([A-Za-z0-9_-]+)/jobs/(\d+)", parsed.path)
    if not match:
        return None
    return match.group(1), match.group(2)


def parse_lever(url: str):
    parsed = urlparse(url)
    if parsed.netloc.lower() != "jobs.lever.co":
        return None
    match = re.search(r"^/([A-Za-z0-9_-]+)/([0-9a-fA-F-]+)", parsed.path)
    if not match:
        return None
    return match.group(1), match.group(2)


def check_greenhouse_open(company: str, posting_id: str) -> bool:
    try:
        resp = httpx.get(
            f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{posting_id}",
            timeout=10,
        )
    except Exception:
        return True
    return resp.status_code == 200


def check_lever_open(company: str, posting_id: str) -> bool:
    try:
        resp = httpx.get(f"https://api.lever.co/v0/postings/{company}/{posting_id}", timeout=10)
    except Exception:
        return True
    return resp.status_code == 200
