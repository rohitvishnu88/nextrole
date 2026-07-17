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


def test_needs_reverify_handles_naive_stored_timestamp_against_aware_now():
    now = datetime.now(timezone.utc)
    naive_last = (now - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    assert job_freshness.needs_reverify(naive_last, now) is False


def test_needs_reverify_exact_24h_boundary_counts_as_due():
    now = datetime.now(timezone.utc)
    last = (now - timedelta(hours=24)).isoformat()
    assert job_freshness.needs_reverify(last, now) is True


def test_looks_closed_empty_string_is_false():
    assert job_freshness.looks_closed("") is False


def test_parse_greenhouse_extracts_company_and_id():
    url = "https://boards.greenhouse.io/acme/jobs/4567890"
    assert job_freshness.parse_greenhouse(url) == ("acme", "4567890")


def test_parse_greenhouse_returns_none_for_non_matching_url():
    assert job_freshness.parse_greenhouse("https://boards.greenhouse.io/acme/about") is None


def test_parse_lever_extracts_company_and_id():
    url = "https://jobs.lever.co/acme/1a2b3c4d-5e6f-7890-abcd-ef1234567890"
    assert job_freshness.parse_lever(url) == ("acme", "1a2b3c4d-5e6f-7890-abcd-ef1234567890")


def test_parse_lever_returns_none_for_non_matching_url():
    assert job_freshness.parse_lever("https://jobs.lever.co/acme") is None


def test_check_greenhouse_open_true_on_200(monkeypatch):
    class FakeResponse:
        status_code = 200

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr(job_freshness.httpx, "get", fake_get)
    assert job_freshness.check_greenhouse_open("acme", "123") is True


def test_check_greenhouse_open_false_on_404(monkeypatch):
    class FakeResponse:
        status_code = 404

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr(job_freshness.httpx, "get", fake_get)
    assert job_freshness.check_greenhouse_open("acme", "123") is False


def test_check_lever_open_true_on_200(monkeypatch):
    class FakeResponse:
        status_code = 200

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr(job_freshness.httpx, "get", fake_get)
    assert job_freshness.check_lever_open("acme", "abc") is True
