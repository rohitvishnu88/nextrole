import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


@pytest.fixture
def usage(tmp_path, monkeypatch):
    monkeypatch.setenv("APPLICATIONS_DB", str(tmp_path / "app.db"))
    import core.usage as mod
    importlib.reload(mod)
    return mod


def test_reserve_until_user_limit_then_limit_reached(usage):
    for _ in range(4):
        rid = usage.reserve("u1", "job_search", is_owner=False, now=NOW)
        usage.commit(rid)
    with pytest.raises(usage.LimitReached) as exc:
        usage.reserve("u1", "job_search", is_owner=False, now=NOW)
    assert exc.value.code == "limit_reached"
    assert exc.value.action == "job_search"
    assert exc.value.resets_on == "2026-11-01"
    usage.reserve("u2", "job_search", is_owner=False, now=NOW)  # other users unaffected


def test_owner_exempt_from_user_limit(usage):
    for _ in range(10):
        usage.commit(usage.reserve("owner", "job_search", is_owner=True, now=NOW))


def test_release_does_not_count_against_allowance_but_cost_counts_to_budget(usage):
    rid = usage.reserve("u1", "tailor", is_owner=False, now=NOW)
    usage.record_call(rid, model="claude-sonnet-4-6", input_tokens=100_000, output_tokens=0)
    usage.release(rid)
    assert usage.counts_for("u1", "2026-10").get("tailor", 0) == 0
    assert usage.spent_this_month(now=NOW) == pytest.approx(0.30)


def test_in_flight_estimates_block_budget(usage):
    filler = usage.reserve("owner", "cli", is_owner=True, now=NOW)
    usage.record_call(filler, model="claude-sonnet-4-6", output_tokens=3_166_667)  # ~$47.50
    usage.commit(filler)
    for user in ("a", "b", "c", "d"):
        usage.reserve(user, "job_search", is_owner=False, now=NOW)  # 4 x 0.60 held in flight
    with pytest.raises(usage.LimitReached) as exc:
        usage.reserve("e", "job_search", is_owner=False, now=NOW)
    assert exc.value.code == "budget_reached"


def test_commit_replaces_estimate_with_measured_cost(usage):
    rid = usage.reserve("u1", "job_search", is_owner=False, now=NOW)
    assert usage.spent_this_month(now=NOW) == pytest.approx(0.60)
    usage.record_call(rid, tavily_credits=10)
    usage.commit(rid)
    assert usage.spent_this_month(now=NOW) == pytest.approx(0.08)


def test_record_call_prices_tokens_and_tavily_credits(usage):
    rid = usage.reserve("u1", "search_brief", is_owner=False, now=NOW)
    usage.record_call(rid, model="claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000,
                      cache_read_tokens=1_000_000, cache_write_tokens=1_000_000)
    usage.record_call(rid, tavily_credits=5)
    usage.commit(rid)
    # 1 + 5 + 0.1 + 1.25 + 5 * 0.008
    assert usage.spent_this_month(now=NOW) == pytest.approx(7.39)


def test_month_rollover_resets_counts(usage):
    for _ in range(4):
        usage.commit(usage.reserve("u1", "job_search", is_owner=False, now=NOW))
    usage.reserve("u1", "job_search", is_owner=False, now=datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert usage.resets_on("2026-12") == "2027-01-01"
    assert usage.month_of(NOW) == "2026-10"
