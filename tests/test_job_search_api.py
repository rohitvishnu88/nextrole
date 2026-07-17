import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path / "output"))
    profile_dir = tmp_path / "profiles" / "test-user"
    profile_dir.mkdir(parents=True)
    (profile_dir / "resume_data.json").write_text(json.dumps({"name": "Test User"}))
    return tmp_path


@pytest.fixture
def client(dirs, monkeypatch):
    import importlib
    import a2a.routes.job_search as mod
    importlib.reload(mod)
    monkeypatch.setattr(mod.job_search_agent, "run", lambda resume, profile_slug="": {
        "generated_at": "2026-07-17T00:00:00", "jobs": [],
    })
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app), mod


def test_start_search_404_when_no_resume(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/unknown-user/job-search")
    assert resp.status_code == 404


def test_start_search_returns_searching_status(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/test-user/job-search")
    assert resp.status_code == 200
    assert resp.json() == {"status": "searching"}


def test_start_search_409_when_already_running(client):
    test_client, mod = client
    mod._running.add("test-user")
    resp = test_client.post("/api/profiles/test-user/job-search")
    assert resp.status_code == 409
    mod._running.discard("test-user")


def test_get_job_search_returns_searching_while_running(client):
    test_client, mod = client
    mod._running.add("test-user")
    resp = test_client.get("/api/profiles/test-user/job-search")
    assert resp.json() == {"status": "searching"}
    mod._running.discard("test-user")


def test_get_job_search_returns_jobs_when_idle(client, dirs):
    test_client, mod = client
    import job_store
    store = job_store.load_store("test-user")
    job_store.merge_job(store, {
        "source": "greenhouse", "title": "Data Engineer", "company": "Acme",
        "location": "London", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "relevance_score": 8, "match_reason": "fits",
    }, "2026-07-17T00:00:00")
    job_store.save_store("test-user", store)

    resp = test_client.get("/api/profiles/test-user/job-search")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["status"] == "new"

    resp2 = test_client.get("/api/profiles/test-user/job-search")
    assert resp2.json()["jobs"][0]["status"] == "seen"


def test_apply_to_job_marks_status(client, dirs):
    test_client, mod = client
    import job_store
    store = job_store.load_store("test-user")
    job_store.merge_job(store, {
        "source": "greenhouse", "title": "Data Engineer", "company": "Acme",
        "location": "London", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "relevance_score": 8, "match_reason": "fits",
    }, "2026-07-17T00:00:00")
    job_store.save_store("test-user", store)
    job_id = list(store["jobs"].keys())[0]

    resp = test_client.post(f"/api/profiles/test-user/job-search/{job_id}/apply")
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


def test_dismiss_job_404_for_unknown_id(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/test-user/job-search/unknown-id/dismiss")
    assert resp.status_code == 404


def test_start_search_400_for_invalid_slug(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/../job-search")
    assert resp.status_code in (400, 404)


def test_get_job_search_400_for_invalid_slug(client):
    test_client, mod = client
    resp = test_client.get("/api/profiles/bad_slug!/job-search")
    assert resp.status_code == 400


def test_get_job_search_surfaces_last_error(client, dirs):
    test_client, mod = client
    mod._last_error["test-user"] = "simulated crash: RuntimeError"
    resp = test_client.get("/api/profiles/test-user/job-search")
    assert resp.json()["error"] == "simulated crash: RuntimeError"
    mod._last_error.pop("test-user", None)


def test_get_job_search_error_is_none_when_no_failure(client, dirs):
    test_client, mod = client
    resp = test_client.get("/api/profiles/test-user/job-search")
    assert resp.json()["error"] is None
