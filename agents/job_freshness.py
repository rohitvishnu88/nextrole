"""Freshness verification for job postings: closure detection and re-verify cadence."""
from datetime import datetime, timedelta, timezone

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
