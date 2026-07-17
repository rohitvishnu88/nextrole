# tests/test_job_freshness.py
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import job_freshness


def test_looks_closed_detects_linkedin_phrase():
    text = "Senior Data Engineer at Acme. No longer accepting applications."
    assert job_freshness.looks_closed(text) is True


def test_looks_closed_detects_filled_phrase():
    assert job_freshness.looks_closed("This position has been filled.") is True


def test_looks_closed_false_for_normal_listing():
    text = "Senior Data Engineer at Acme. Apply now. We are hiring across the UK."
    assert job_freshness.looks_closed(text) is False


def test_looks_closed_case_insensitive():
    assert job_freshness.looks_closed("NO LONGER ACCEPTING APPLICATIONS") is True


def test_needs_reverify_true_when_never_verified():
    assert job_freshness.needs_reverify("", datetime.now(timezone.utc)) is True


def test_needs_reverify_false_within_24h():
    now = datetime.now(timezone.utc)
    last = (now - timedelta(hours=2)).isoformat()
    assert job_freshness.needs_reverify(last, now) is False


def test_needs_reverify_true_after_24h():
    now = datetime.now(timezone.utc)
    last = (now - timedelta(hours=25)).isoformat()
    assert job_freshness.needs_reverify(last, now) is True
