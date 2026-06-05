import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    p_dir = tmp_path / "profiles" / "test-user"
    p_dir.mkdir(parents=True)
    resume = {
        "name": "Test User",
        "summary": "Senior data engineer with 10 years experience.",
        "experience": [
            {"title": "Data Engineer", "company": "Acme", "description": ["Built pipelines"]}
        ],
        "skills": {"Cloud": ["AWS", "GCP"]},
        "education": [],
        "certifications": [],
        "work_right": "UK citizen",
    }
    (p_dir / "resume_data.json").write_text(json.dumps(resume))
    return tmp_path / "profiles"


@pytest.fixture
def client(profiles_dir):
    import importlib
    import a2a.routes.search_brief as mod
    importlib.reload(mod)
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_get_brief_404_when_not_generated(client):
    resp = client.get("/api/profiles/test-user/search-brief")
    assert resp.status_code == 404


def test_get_brief_returns_saved_brief(client, profiles_dir):
    brief = {
        "generated_at": "2026-05-31T00:00:00",
        "headline": "Test headline",
        "signals": [
            {"id": "abc", "category": "roles", "label": "Data Engineer",
             "confidence": "high", "source": "Job title", "active": True}
        ]
    }
    (profiles_dir / "test-user" / "search_brief.json").write_text(json.dumps(brief))
    resp = client.get("/api/profiles/test-user/search-brief")
    assert resp.status_code == 200
    assert resp.json()["headline"] == "Test headline"
    assert len(resp.json()["signals"]) == 1


def test_patch_signal_toggles_active(client, profiles_dir):
    brief = {
        "generated_at": "2026-05-31T00:00:00",
        "headline": "Test",
        "signals": [
            {"id": "abc", "category": "roles", "label": "Data Engineer",
             "confidence": "high", "source": "Job title", "active": True}
        ]
    }
    (profiles_dir / "test-user" / "search_brief.json").write_text(json.dumps(brief))
    resp = client.patch("/api/profiles/test-user/search-brief/signals/abc", json={"active": False})
    assert resp.status_code == 200
    updated = client.get("/api/profiles/test-user/search-brief").json()
    assert updated["signals"][0]["active"] is False


def test_patch_signal_404_unknown_id(client, profiles_dir):
    brief = {"generated_at": "2026-05-31", "headline": "T", "signals": []}
    (profiles_dir / "test-user" / "search_brief.json").write_text(json.dumps(brief))
    resp = client.patch("/api/profiles/test-user/search-brief/signals/nonexistent", json={"active": False})
    assert resp.status_code == 404
