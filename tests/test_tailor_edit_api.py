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


def test_get_cover_letter_text(client):
    c, mod = client
    resp = c.get("/api/tailor/test-job-id/cover-letter-text")
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Cover letter text."


def test_patch_data_updates_json_and_cover_letter(client, tmp_path, monkeypatch):
    c, mod = client

    # Mock render_resume so we don't need Playwright in tests
    import resume_builder
    monkeypatch.setattr(resume_builder, "render_resume", lambda data, html, pdf: None)

    updated_resume = {"name": "Test User", "summary": "Updated summary.", "experience": []}
    resp = c.patch("/api/tailor/test-job-id/data", json={
        "resume": updated_resume,
        "cover_letter": "Updated cover letter.",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify the JSON file on disk was overwritten
    import json as _json
    job = mod._jobs["test-job-id"]
    written = _json.loads(Path(job["json_file"]).read_text())
    assert written["summary"] == "Updated summary."

    # Verify the cover letter was overwritten
    assert Path(job["cover_letter_file"]).read_text() == "Updated cover letter."


def test_patch_data_404_for_unknown_job(client):
    c, _ = client
    resp = c.patch("/api/tailor/no-such-id/data", json={"resume": {}, "cover_letter": None})
    assert resp.status_code == 404
