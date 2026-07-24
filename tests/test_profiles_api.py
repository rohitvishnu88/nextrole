# tests/test_profiles_api.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    return tmp_path / "profiles"


@pytest.fixture
def client(profiles_dir):
    import importlib
    import a2a.routes.profiles as mod
    importlib.reload(mod)
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_normalize_skills_passes_through_correct_shape():
    import a2a.routes.profiles as mod
    result = mod._normalize_skills({"Cloud": ["AWS", "GCP"]})
    assert result == {"Cloud": ["AWS", "GCP"]}


def test_normalize_skills_wraps_flat_list():
    import a2a.routes.profiles as mod
    result = mod._normalize_skills(["Leadership", "Marketing Strategy"])
    assert result == {"Skills": ["Leadership", "Marketing Strategy"]}


def test_normalize_skills_wraps_non_list_group_value():
    import a2a.routes.profiles as mod
    result = mod._normalize_skills({"Cloud": "AWS"})
    assert result == {"Cloud": ["AWS"]}


def test_normalize_skills_handles_none_or_missing():
    import a2a.routes.profiles as mod
    assert mod._normalize_skills(None) == {}
    assert mod._normalize_skills("") == {}


def test_list_profiles_empty(client):
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_profile(client):
    resp = client.post("/api/profiles", json={"name": "Rohit", "slug": "rohit"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "rohit"
    assert data["name"] == "Rohit"


def test_create_duplicate_slug_returns_409(client):
    client.post("/api/profiles", json={"name": "Rohit", "slug": "rohit"})
    resp = client.post("/api/profiles", json={"name": "Rohit2", "slug": "rohit"})
    assert resp.status_code == 409


def test_delete_profile(client):
    client.post("/api/profiles", json={"name": "Temp", "slug": "temp"})
    resp = client.delete("/api/profiles/temp")
    assert resp.status_code == 200
    assert client.get("/api/profiles").json() == []


def test_confirm_resume_pushes_history_before_overwriting(client, profiles_dir):
    import io
    from unittest.mock import patch

    slug = "rohit"
    client.post("/api/profiles", json={"name": "Rohit", "slug": slug})
    (profiles_dir / slug / "resume_data.json").write_text(
        json.dumps({"name": "Old Resume"}), encoding="utf-8"
    )

    class _FakeContent:
        text = '{"name": "New Resume"}'

    class _FakeResponse:
        content = [_FakeContent()]

    class _FakeMessages:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeClient:
        def __init__(self):
            self.messages = _FakeMessages()

    with patch("anthropic.Anthropic", lambda: _FakeClient()), \
         patch("pdfplumber.open") as mock_pdf:
        mock_page = type("P", (), {"extract_text": lambda self: "resume text"})()
        mock_pdf.return_value.__enter__.return_value.pages = [mock_page]
        resp = client.post(
            f"/api/profiles/{slug}/resume/parse",
            files={"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
    assert resp.status_code == 200

    resp = client.post(f"/api/profiles/{slug}/resume/confirm")
    assert resp.status_code == 200

    resume = json.loads((profiles_dir / slug / "resume_data.json").read_text())
    assert resume == {"name": "New Resume", "skills": {}}

    history = json.loads((profiles_dir / slug / "resume_history.json").read_text())
    assert len(history["versions"]) == 1
    assert history["versions"][0]["change_summary"] == "Replaced via file upload"
    assert history["versions"][0]["data"] == {"name": "Old Resume"}
