import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from auth_helpers import OWNER, sign_in

import pytest


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_applications.db"
    monkeypatch.setenv("APPLICATIONS_DB", str(db_path))
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    (tmp_path / "profiles" / "rohit").mkdir(parents=True)
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
    sign_in(app, OWNER)
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


# --- follow-ups and score columns ---

import sqlite3
from datetime import date, timedelta

OLD_SCHEMA = """
    CREATE TABLE applications (
        id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, job_title TEXT NOT NULL,
        company TEXT NOT NULL, location TEXT, url TEXT,
        status TEXT NOT NULL DEFAULT 'saved', applied_date TEXT, notes TEXT,
        resume_file TEXT, cover_letter_file TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )
"""


def test_migration_adds_columns_to_old_db(tmp_db, tmp_path):
    db_path = tmp_db._get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute(OLD_SCHEMA)
    conn.execute("INSERT INTO applications VALUES ('a1','rohit','Architect','Acme',NULL,NULL,'saved',NULL,NULL,NULL,NULL,'t','t')")
    conn.commit()
    conn.close()

    tmp_db.init_db()
    tmp_db.init_db()

    rows = tmp_db.list_applications("rohit")
    assert len(rows) == 1 and rows[0]["job_title"] == "Architect"
    assert {"follow_up_date", "match_score", "analysis_id"} <= set(rows[0])


def test_create_applied_sets_dates(api_client):
    app = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Architect", "company": "Acme", "status": "applied",
    }).json()
    today = date.today()
    assert app["applied_date"] == today.isoformat()
    assert app["follow_up_date"] == (today + timedelta(days=7)).isoformat()


def test_patch_to_applied_keeps_existing_applied_date(api_client):
    app = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Architect", "company": "Acme",
        "status": "saved", "applied_date": "2026-10-01",
    }).json()
    api_client.patch(f"/api/applications/{app['id']}", json={"status": "applied"})
    row = api_client.get("/api/applications?profile=rohit").json()[0]
    assert row["applied_date"] == "2026-10-01"
    assert row["follow_up_date"] == "2026-10-08"


def test_patch_explicit_null_clears_follow_up(api_client):
    app = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Architect", "company": "Acme",
        "status": "applied", "notes": "keep me",
    }).json()
    api_client.patch(f"/api/applications/{app['id']}", json={"follow_up_date": None})
    api_client.patch(f"/api/applications/{app['id']}", json={})
    row = api_client.get("/api/applications?profile=rohit").json()[0]
    assert row["follow_up_date"] is None
    assert row["notes"] == "keep me"


def test_followed_up_endpoint_moves_date(api_client):
    app = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Architect", "company": "Acme", "status": "applied",
    }).json()
    resp = api_client.post(f"/api/applications/{app['id']}/followed-up")
    assert resp.status_code == 200
    assert resp.json() == {"follow_up_date": (date.today() + timedelta(days=7)).isoformat()}
    assert api_client.post("/api/applications/nope/followed-up").status_code == 404


def test_overdue_flag(api_client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    for status in ("applied", "rejected"):
        app = api_client.post("/api/applications", json={
            "profile_id": "rohit", "job_title": status, "company": "Acme", "status": status,
        }).json()
        api_client.patch(f"/api/applications/{app['id']}", json={"follow_up_date": yesterday})
    rows = {r["job_title"]: r for r in api_client.get("/api/applications?profile=rohit").json()}
    assert rows["applied"]["overdue"] is True
    assert rows["rejected"]["overdue"] is False


def test_patch_null_required_field_rejected(api_client):
    app = api_client.post("/api/applications", json={
        "profile_id": "rohit", "job_title": "Architect", "company": "Acme", "status": "saved",
    }).json()
    resp = api_client.patch(f"/api/applications/{app['id']}", json={"company": None})
    assert resp.status_code == 400
