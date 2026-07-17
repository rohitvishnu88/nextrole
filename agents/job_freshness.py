"""Freshness verification for job postings: closure detection and re-verify cadence."""
from datetime import datetime, timedelta

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
    if not last_verified_at_iso:
        return True
    last_verified = datetime.fromisoformat(last_verified_at_iso)
    return now - last_verified >= REVERIFY_INTERVAL
