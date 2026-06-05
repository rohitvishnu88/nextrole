import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_applications.db"
    monkeypatch.setenv("APPLICATIONS_DB", str(db_path))
    import importlib
    import a2a.db as db_module
    importlib.reload(db_module)
    yield db_module


def test_create_and_get_application(tmp_db):
    app_id = tmp_db.create_application(
        profile_id="rohit",
        job_title="Data Architect",
        company="Acme",
        location="London",
        url="https://example.com/job/1",
        status="applied",
        applied_date="2026-05-30",
        notes="Good match",
        resume_file=None,
        cover_letter_file=None,
    )
    assert app_id is not None
    apps = tmp_db.list_applications("rohit")
    assert len(apps) == 1
    assert apps[0]["company"] == "Acme"
    assert apps[0]["status"] == "applied"


def test_update_application_status(tmp_db):
    app_id = tmp_db.create_application(
        profile_id="rohit", job_title="Engineer", company="Beta",
        location="Remote", url=None, status="applied",
        applied_date=None, notes=None, resume_file=None, cover_letter_file=None,
    )
    tmp_db.update_application(app_id, {"status": "interview"})
    apps = tmp_db.list_applications("rohit")
    assert apps[0]["status"] == "interview"


def test_delete_application(tmp_db):
    app_id = tmp_db.create_application(
        profile_id="rohit", job_title="Analyst", company="Gamma",
        location="London", url=None, status="saved",
        applied_date=None, notes=None, resume_file=None, cover_letter_file=None,
    )
    tmp_db.delete_application(app_id)
    assert tmp_db.list_applications("rohit") == []


# --- FastAPI route tests ---

@pytest.fixture
def api_client(tmp_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import importlib
    import a2a.routes.applications as mod
    importlib.reload(mod)
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_api_create_and_list(api_client):
    resp = api_client.post("/api/applications", json={
        "profile_id": "rohit",
        "job_title": "Data Architect",
        "company": "Acme",
        "location": "London",
        "status": "applied",
    })
    assert resp.status_code == 200
    app_id = resp.json()["id"]

    resp = api_client.get("/api/applications?profile=rohit")
    assert resp.status_code == 200
    assert any(a["id"] == app_id for a in resp.json())


def test_api_patch_status(api_client):
    resp = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Engineer",
        "company": "Beta", "status": "saved",
    })
    app_id = resp.json()["id"]

    resp = api_client.patch(f"/api/applications/{app_id}", json={"status": "interview"})
    assert resp.status_code == 200

    apps = api_client.get("/api/applications?profile=rohit").json()
    assert apps[0]["status"] == "interview"


def test_api_delete(api_client):
    resp = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Analyst",
        "company": "Gamma", "status": "saved",
    })
    app_id = resp.json()["id"]
    api_client.delete(f"/api/applications/{app_id}")
    apps = api_client.get("/api/applications?profile=rohit").json()
    assert not any(a["id"] == app_id for a in apps)
