import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    p = tmp_path / "profiles" / "test-user"
    p.mkdir(parents=True)
    (p / "resume_data.json").write_text(json.dumps({
        "name": "Test User",
        "summary": "A summary.",
        "experience": [{"title": "Data Engineer", "company": "Acme", "description": ["Built things"]}],
        "education": [{"degree": "BSc", "school": "Uni"}],
        "certifications": [{"name": "AWS SA", "issuer": "AWS"}],
        "languages": ["English"],
        "skills": {"Cloud": ["AWS", "GCP"]},
    }))
    return tmp_path / "profiles"


@pytest.fixture
def client(profiles_dir):
    import importlib
    import a2a.routes.resume_versions as mod
    importlib.reload(mod)
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_list_history_empty_when_no_changes_yet(client):
    resp = client.get("/api/profiles/test-user/resume/history")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_history_version_404_when_missing(client):
    resp = client.get("/api/profiles/test-user/resume/history/nonexistent")
    assert resp.status_code == 404


def test_restore_404_when_version_missing(client):
    resp = client.post("/api/profiles/test-user/resume/history/nonexistent/restore")
    assert resp.status_code == 404


def test_history_list_and_restore_round_trip(client, profiles_dir):
    import a2a.resume_history as rh
    rh.push_version("test-user", "Manual snapshot for test")

    resp = client.get("/api/profiles/test-user/resume/history")
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 1
    assert versions[0]["change_summary"] == "Manual snapshot for test"
    assert "data" not in versions[0]

    version_id = versions[0]["id"]
    resp = client.get(f"/api/profiles/test-user/resume/history/{version_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Test User"

    (profiles_dir / "test-user" / "resume_data.json").write_text(
        json.dumps({"name": "Changed"})
    )

    resp = client.post(f"/api/profiles/test-user/resume/history/{version_id}/restore")
    assert resp.status_code == 200

    current = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert current["name"] == "Test User"
