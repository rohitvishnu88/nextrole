import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth_helpers import FRIEND, OWNER, sign_in
from core import usage


@pytest.fixture
def make():
    import importlib
    import a2a.routes.usage_api as mod
    importlib.reload(mod)

    def _make(user):
        app = FastAPI()
        app.include_router(mod.router)
        sign_in(app, user)
        return TestClient(app)
    return _make


def test_usage_me_for_friend_has_limits_no_owner_block(make):
    usage.commit(usage.reserve(FRIEND.id, "tailor", is_owner=False))
    body = make(FRIEND).get("/api/usage/me").json()
    assert body["month"] == usage.month_of()
    assert body["resets_on"] == usage.resets_on(usage.month_of())
    assert body["paused"] is False
    assert body["actions"]["tailor"] == {"used": 1, "limit": 12}
    assert body["actions"]["job_search"] == {"used": 0, "limit": 4}
    assert "owner" not in body


def test_usage_me_for_owner_has_spend_breakdown(make):
    from a2a import db
    db.upsert_user(FRIEND.email, "Friend", "", False)
    friend_id = db.get_user_by_email(FRIEND.email)["id"]
    rid = usage.reserve(friend_id, "tailor", is_owner=False)
    usage.record_call(rid, tavily_credits=100)
    usage.commit(rid)
    body = make(OWNER).get("/api/usage/me").json()
    assert body["actions"]["tailor"]["limit"] is None
    owner = body["owner"]
    assert owner["budget_usd"] == 50.0
    assert owner["spent_usd"] == pytest.approx(0.80)
    assert owner["by_user"] == [{"email": FRIEND.email, "spent_usd": pytest.approx(0.80), "counts": {"tailor": 1}}]
    assert owner["by_action"] == {"tailor": pytest.approx(0.80)}


def test_paused_true_at_ceiling(make, monkeypatch):
    monkeypatch.setattr(usage.limits, "MONTHLY_BUDGET_USD", 0.0)
    assert make(FRIEND).get("/api/usage/me").json()["paused"] is True
