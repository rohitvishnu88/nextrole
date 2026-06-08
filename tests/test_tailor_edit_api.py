# tests/test_tailor_edit_api.py
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path):
    # Reload the module so _jobs starts empty each test
    import importlib
    import a2a.routes.tailor_api as mod
    importlib.reload(mod)

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    # Seed a completed job with real temp files
    resume = {"name": "Test User", "summary": "A summary.", "experience": []}
    json_file = tmp_path / "resume.json"
    json_file.write_text(json.dumps(resume))

    cover_letter_file = tmp_path / "cover.txt"
    cover_letter_file.write_text("Cover letter text.")

    html_file = tmp_path / "resume.html"
    html_file.write_text("<html></html>")

    pdf_file = tmp_path / "resume.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")

    mod._jobs["test-job-id"] = {
        "status": "completed",
        "message": "Done",
        "profile_slug": "rohit",
        "json_file": str(json_file),
        "pdf_file": str(pdf_file),
        "cover_letter_file": str(cover_letter_file),
        "url": "https://example.com/job",
    }

    return client, mod


def test_status_includes_json_file(client):
    c, mod = client
    resp = c.get("/api/tailor/test-job-id")
    assert resp.status_code == 200
    data = resp.json()
    assert "json_file" in data
    assert data["json_file"].endswith("resume.json")


def test_get_data_returns_resume_json(client):
    c, mod = client
    resp = c.get("/api/tailor/test-job-id/data")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test User"
    assert data["summary"] == "A summary."


def test_get_data_404_for_unknown_job(client):
    c, _ = client
    resp = c.get("/api/tailor/no-such-id/data")
    assert resp.status_code == 404
