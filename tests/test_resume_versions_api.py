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


def test_apply_add_list_object_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/experience/apply",
        json={"action": "add", "item": [{"title": "New Role", "company": "NewCo", "description": ["Did stuff"]}]},
    )
    assert resp.status_code == 200
    assert resp.json()["change_summary"] == "Added Experience: New Role"

    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert len(resume["experience"]) == 2
    assert resume["experience"][1]["title"] == "New Role"

    history = json.loads((profiles_dir / "test-user" / "resume_history.json").read_text())
    assert len(history["versions"]) == 1
    assert len(history["versions"][0]["data"]["experience"]) == 1


def test_apply_edit_list_object_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/experience/apply",
        json={"action": "edit", "item_index": 0, "item": {"title": "Updated Title", "company": "Acme", "description": ["Changed"]}},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["experience"][0]["title"] == "Updated Title"


def test_apply_edit_list_object_out_of_range_index(client):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/experience/apply",
        json={"action": "edit", "item_index": 9, "item": {"title": "X"}},
    )
    assert resp.status_code == 400


def test_apply_delete_list_object_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/certifications/apply",
        json={"action": "delete", "item_index": 0},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["certifications"] == []


def test_apply_add_flat_list_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/languages/apply",
        json={"action": "add", "item": ["French", "German"]},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["languages"] == ["English", "French", "German"]


def test_apply_delete_flat_list_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/languages/apply",
        json={"action": "delete", "item_index": 0},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["languages"] == []


def test_apply_add_grouped_list_new_group(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "add", "item": [{"group": "Programming", "skill": "Python"}]},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["skills"]["Programming"] == ["Python"]
    assert resume["skills"]["Cloud"] == ["AWS", "GCP"]


def test_apply_edit_grouped_list_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "edit", "group": "Cloud", "skill": "GCP", "item": {"group": "Cloud", "skill": "Azure"}},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["skills"]["Cloud"] == ["AWS", "Azure"]


def test_apply_delete_grouped_list_removes_empty_group(client, profiles_dir):
    client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "delete", "group": "Cloud", "skill": "AWS"},
    )
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "delete", "group": "Cloud", "skill": "GCP"},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert "Cloud" not in resume["skills"]


def test_apply_delete_grouped_list_unknown_skill_400(client):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "delete", "group": "Cloud", "skill": "Nonexistent"},
    )
    assert resp.status_code == 400


def test_apply_edit_scalar_section(client, profiles_dir):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/summary/apply",
        json={"action": "edit", "item": "A new summary."},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["summary"] == "A new summary."


def test_apply_scalar_rejects_add_action(client):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/summary/apply",
        json={"action": "add", "item": "X"},
    )
    assert resp.status_code == 400


def test_apply_unknown_section_400(client):
    resp = client.post(
        "/api/profiles/test-user/resume/sections/nonexistent/apply",
        json={"action": "edit", "item": "X"},
    )
    assert resp.status_code == 400


def test_apply_edit_grouped_list_different_group_skill_moves(client, profiles_dir):
    """Verify skill can move to a genuinely different group, leaving original group non-empty."""
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "edit", "group": "Cloud", "skill": "GCP", "item": {"group": "Programming", "skill": "GCP"}},
    )
    assert resp.status_code == 200
    resume = json.loads((profiles_dir / "test-user" / "resume_data.json").read_text())
    assert resume["skills"]["Cloud"] == ["AWS"]
    assert resume["skills"]["Programming"] == ["GCP"]


def test_apply_edit_grouped_list_different_group_empties_original(profiles_dir, monkeypatch):
    """Verify skill move deletes original group if it becomes empty."""
    # Create a profile with a single-skill group to test empty group removal
    p = profiles_dir / "empty-test-user"
    p.mkdir(parents=True)
    (p / "resume_data.json").write_text(json.dumps({
        "name": "Test User",
        "summary": "A summary.",
        "experience": [],
        "education": [],
        "certifications": [],
        "languages": [],
        "skills": {"Cloud": ["GCP"], "Programming": ["Python"]},
    }))

    # Reload module to pick up new fixture data
    import importlib
    import a2a.routes.resume_versions as mod
    importlib.reload(mod)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    resp = client.post(
        "/api/profiles/empty-test-user/resume/sections/skills/apply",
        json={"action": "edit", "group": "Cloud", "skill": "GCP", "item": {"group": "Programming", "skill": "GCP"}},
    )
    assert resp.status_code == 200
    resume = json.loads((p / "resume_data.json").read_text())
    assert "Cloud" not in resume["skills"]
    assert resume["skills"]["Programming"] == ["Python", "GCP"]


def test_apply_add_grouped_list_missing_skill_key(client):
    """Verify add action validates presence of skill key."""
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "add", "item": [{"group": "Programming"}]},
    )
    assert resp.status_code == 400


def test_apply_add_grouped_list_missing_group_key(client):
    """Verify add action validates presence of group key."""
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "add", "item": [{"skill": "Python"}]},
    )
    assert resp.status_code == 400


def test_apply_edit_grouped_list_missing_group_key(client):
    """Verify edit action validates presence of group key in item."""
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "edit", "group": "Cloud", "skill": "GCP", "item": {"skill": "Java"}},
    )
    assert resp.status_code == 400


def test_apply_edit_grouped_list_missing_skill_key(client):
    """Verify edit action validates presence of skill key in item."""
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/apply",
        json={"action": "edit", "group": "Cloud", "skill": "GCP", "item": {"group": "Programming"}},
    )
    assert resp.status_code == 400
