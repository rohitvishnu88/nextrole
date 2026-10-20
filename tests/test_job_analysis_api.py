import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from auth_helpers import OWNER, sign_in
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

JOB_URL = "https://jobs.lever.co/acme/123"
JD = "Senior Integration Architect at Acme. " * 40


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path / "output"))
    profile_dir = tmp_path / "profiles" / "test-user"
    profile_dir.mkdir(parents=True)
    (profile_dir / "resume_data.json").write_text(json.dumps({"name": "Test User"}))

    import importlib
    import job_store
    import job_analysis
    import a2a.routes.job_analysis as mod
    importlib.reload(mod)
    monkeypatch.setattr(job_analysis, "ROOT", tmp_path)

    store = {"jobs": {}}
    job_store.merge_job(store, {"url": JOB_URL, "source": "lever", "title": "Architect", "company": "Acme"}, "2026-10-20T00:00:00")
    job_store.save_store("test-user", store)
    job_id = job_store.make_job_id(JOB_URL)

    calls = []
    saved = set()

    def fake_analysis(client, slug, resume, jd_text, source_url=None):
        calls.append(jd_text)
        if len(jd_text) < job_analysis.MIN_JD_CHARS:
            raise job_analysis.JobTextTooShort("Couldn't read the full job ad. Tailor it with the ad text pasted instead.")
        saved.add("0123456789abcdef")
        return {"analysis_id": "0123456789abcdef", "match_score": 80, "verdict": "strong fit"}

    monkeypatch.setattr(mod, "_fetch_job_text_with_source", lambda url: (JD, "page"))
    monkeypatch.setattr(mod, "_make_client", lambda: object())
    monkeypatch.setattr(mod.job_analysis, "get_or_create_analysis", fake_analysis)
    # Only analyses the fake actually produced exist, like the real on-disk cache.
    monkeypatch.setattr(mod.job_analysis, "load_analysis",
                        lambda slug, aid: {"analysis_id": aid, "match_score": 80, "verdict": "strong fit"} if aid in saved else None)

    app = FastAPI()
    app.include_router(mod.router)
    sign_in(app, OWNER)
    return TestClient(app), mod, job_id, calls


def test_analyse_then_ready(setup):
    client, mod, job_id, calls = setup
    assert client.get(f"/api/profiles/test-user/job-search/{job_id}/analysis").json() == {"status": "none"}
    resp = client.post(f"/api/profiles/test-user/job-search/{job_id}/analyse")
    assert resp.json() == {"status": "analysing"}
    result = client.get(f"/api/profiles/test-user/job-search/{job_id}/analysis").json()
    assert result["status"] == "ready"
    assert result["analysis"]["match_score"] == 80
    assert calls == [JD]


def test_second_analyse_while_running_does_not_start_again(setup):
    client, mod, job_id, calls = setup
    mod._running.add(("test-user", job_id))
    resp = client.post(f"/api/profiles/test-user/job-search/{job_id}/analyse")
    assert resp.json() == {"status": "analysing"}
    assert calls == []
    assert client.get(f"/api/profiles/test-user/job-search/{job_id}/analysis").json() == {"status": "analysing"}


def test_short_text_reports_failed_with_message(setup, monkeypatch):
    client, mod, job_id, calls = setup
    monkeypatch.setattr(mod, "_fetch_job_text_with_source", lambda url: ("Sign in to view", "page"))
    client.post(f"/api/profiles/test-user/job-search/{job_id}/analyse")
    result = client.get(f"/api/profiles/test-user/job-search/{job_id}/analysis").json()
    assert result == {"status": "failed", "error": "Couldn't read the full job ad. Tailor it with the ad text pasted instead."}


def test_unknown_job_404(setup):
    client, *_ = setup
    assert client.post("/api/profiles/test-user/job-search/nope/analyse").status_code == 404


def test_bad_slug_400(setup):
    client, *_ = setup
    assert client.post("/api/profiles/bad..slug/job-search/x/analyse").status_code == 400


def test_search_fallback_text_reports_failed(setup, monkeypatch):
    client, mod, job_id, calls = setup
    monkeypatch.setattr(mod, "_fetch_job_text_with_source", lambda url: (JD, "search"))
    client.post(f"/api/profiles/test-user/job-search/{job_id}/analyse")
    result = client.get(f"/api/profiles/test-user/job-search/{job_id}/analysis").json()
    assert result["status"] == "failed"
    assert calls == []
