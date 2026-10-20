import importlib
import io
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth_helpers import FRIEND, OWNER, sign_in
from core import ai_clients, usage

REPLY = json.dumps({"item": {"text": "x"}, "items": [], "headline": "h", "signals": [], "name": "Friend"})
JOB_URL = "https://jobs.lever.co/acme/1"


class FakeAnthropic:
    def __init__(self):
        self.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[SimpleNamespace(type="text", text=REPLY)],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=1000,
                                  cache_read_input_tokens=0, cache_creation_input_tokens=0)))


def one_claude_call():
    ai_clients.make_anthropic().messages.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])


@pytest.fixture
def env(tmp_path, monkeypatch):
    pdir = tmp_path / "profiles"
    monkeypatch.setenv("PROFILES_DIR", str(pdir))
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path / "out"))
    pdir.mkdir()
    (pdir / "profiles.json").write_text(json.dumps([
        {"id": "1", "name": "Friend", "slug": "friend", "created_at": "t", "owner_user_id": FRIEND.id},
        {"id": "2", "name": "Owner", "slug": "owner", "created_at": "t", "owner_user_id": OWNER.id},
    ]))
    for slug in ("friend", "owner"):
        (pdir / slug).mkdir()
        (pdir / slug / "resume_data.json").write_text(json.dumps({"name": "Friend", "summary": "s", "experience": []}))
    monkeypatch.setattr(ai_clients, "_real_anthropic", FakeAnthropic)

    import job_store
    store = {"jobs": {}}
    job_store.merge_job(store, {"url": JOB_URL, "source": "lever", "title": "A", "company": "B"}, "2026-10-20T00:00:00")
    job_store.save_store("friend", store)

    import a2a.routes.job_search as js
    import a2a.routes.job_analysis as ja
    import a2a.routes.tailor_api as ta
    import a2a.routes.resume_versions as rv
    import a2a.routes.profiles as pr
    import a2a.routes.search_brief as sb
    mods = (js, ja, ta, rv, pr, sb)
    for m in mods:
        importlib.reload(m)

    monkeypatch.setattr(js.job_search_agent, "run", lambda resume, profile_slug="", send_email=True: one_claude_call())
    monkeypatch.setattr(ja, "_fetch_job_text_with_source", lambda url: ("Job ad " * 300, "page"))

    def fake_analysis(client, slug, resume, jd_text, source_url=None):
        client.messages.create(model="claude-sonnet-4-6", max_tokens=10, messages=[])
        return {"analysis_id": "0123456789abcdef"}
    monkeypatch.setattr(ja.job_analysis, "get_or_create_analysis", fake_analysis)

    import tailor_agent
    tailor_calls = {"fail": False}

    def fake_tailor(job_url="", jd_text="", profile_slug=""):
        one_claude_call()
        if tailor_calls["fail"]:
            raise RuntimeError("boom")
        return {"status": "completed", "pdf_file": "p", "cover_letter_file": "c", "json_file": "j"}
    monkeypatch.setattr(tailor_agent, "run", fake_tailor)

    clients = []

    def make(user):
        app = FastAPI()
        for m in mods:
            app.include_router(m.router)
        sign_in(app, user)
        # Entered so the event loop outlives each request and the tailor task can finish.
        client = TestClient(app).__enter__()
        clients.append(client)
        return client
    yield SimpleNamespace(make=make, job_id=job_store.make_job_id(JOB_URL), tailor_calls=tailor_calls, ja=ja)
    for client in clients:
        client.__exit__(None, None, None)


def month():
    return usage.month_of()


def wait_tailor(c, job_id):
    for _ in range(100):
        status = c.get(f"/api/tailor/{job_id}").json()["status"]
        if status != "running":
            return status
        time.sleep(0.02)
    raise AssertionError("tailor never finished")


def test_fifth_job_search_is_429_limit_reached(env):
    c = env.make(FRIEND)
    for _ in range(4):
        assert c.post("/api/profiles/friend/job-search").status_code == 200
    resp = c.post("/api/profiles/friend/job-search")
    assert resp.status_code == 429
    assert resp.json()["detail"] == {"code": "limit_reached", "action": "job_search",
                                     "resets_on": usage.resets_on(month())}


def test_budget_reached_429_for_everyone_including_owner(env, monkeypatch):
    monkeypatch.setattr(usage.limits, "MONTHLY_BUDGET_USD", 0.05)
    for user, slug in ((FRIEND, "friend"), (OWNER, "owner")):
        resp = env.make(user).post(f"/api/profiles/{slug}/job-search")
        assert resp.status_code == 429
        assert resp.json()["detail"]["code"] == "budget_reached"


def test_failed_tailor_releases_allowance(env):
    env.tailor_calls["fail"] = True
    c = env.make(FRIEND)
    job_id = c.post("/api/tailor", json={"profile_slug": "friend", "jd_text": "x"}).json()["job_id"]
    assert wait_tailor(c, job_id) == "failed"
    assert usage.counts_for(FRIEND.id, month()).get("tailor", 0) == 0
    assert usage.spent_this_month() > 0


def test_cached_analysis_does_not_reserve(env, monkeypatch):
    monkeypatch.setattr(env.ja.job_analysis, "load_analysis", lambda slug, aid: {"analysis_id": aid})
    # Like the real get_or_create_analysis, a cached result makes no Claude call.
    monkeypatch.setattr(env.ja.job_analysis, "get_or_create_analysis",
                        lambda client, slug, resume, jd_text, source_url=None: {"analysis_id": "0123456789abcdef"})
    c = env.make(FRIEND)
    assert c.post(f"/api/profiles/friend/job-search/{env.job_id}/analyse").status_code == 200
    assert usage.counts_for(FRIEND.id, month()).get("analyse", 0) == 0
    assert usage.spent_this_month() == 0


ROUTES = [
    ("job_search", lambda c, e: c.post("/api/profiles/friend/job-search")),
    ("analyse", lambda c, e: c.post(f"/api/profiles/friend/job-search/{e.job_id}/analyse")),
    ("tailor", lambda c, e: wait_tailor(c, c.post("/api/tailor", json={"profile_slug": "friend", "jd_text": "x"}).json()["job_id"])),
    ("section_draft", lambda c, e: c.post("/api/profiles/friend/resume/sections/summary/draft",
                                          json={"action": "edit", "instruction": "tighten"})),
    ("resume_parse", lambda c, e: c.post("/api/profiles/friend/resume/parse",
                                         files={"file": ("cv.docx", _docx_bytes(), "application/octet-stream")})),
    ("search_brief", lambda c, e: c.post("/api/profiles/friend/search-brief/generate")),
]


def _docx_bytes():
    import docx
    d = docx.Document()
    d.add_paragraph("Friend — Integration Architect")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize("action,call", ROUTES, ids=[r[0] for r in ROUTES])
def test_each_metered_route_reserves_its_action(env, action, call):
    c = env.make(FRIEND)
    call(c, env)
    assert usage.counts_for(FRIEND.id, month()) == {action: 1}


def test_tailor_calls_metered_against_user_not_cli(env):
    c = env.make(FRIEND)
    wait_tailor(c, c.post("/api/tailor", json={"profile_slug": "friend", "jd_text": "x"}).json()["job_id"])
    actions = usage.summary(month())["by_action"]
    assert "cli" not in actions
    assert actions["tailor"] > 0
