# tests/test_tailor_history_api.py
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


@pytest.fixture
def client(tmp_path, monkeypatch):
    import importlib
    import a2a.routes.tailor_api as mod
    importlib.reload(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    (tmp_path / "profiles" / "rohit").mkdir(parents=True)

    app = FastAPI()
    app.include_router(mod.router)
    sign_in(app, OWNER)
    return TestClient(app), tmp_path


def _write_run(root, slug, entry_id, *, job_url=None, created_at=None, with_pdf=True, with_cover_letter=True):
    resumes_dir = root / "output" / "profiles" / slug / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    (resumes_dir / f"resume_data_{entry_id}.json").write_text(json.dumps({"name": "Test User"}))
    if with_pdf:
        (resumes_dir / f"resume_{entry_id}.pdf").write_bytes(b"%PDF-1.4")
    if job_url is not None or created_at is not None:
        meta = {}
        if job_url is not None:
            meta["job_url"] = job_url
        if created_at is not None:
            meta["created_at"] = created_at
        (resumes_dir / f"meta_{entry_id}.json").write_text(json.dumps(meta))
    if with_cover_letter:
        cl_dir = root / "output" / "profiles" / slug / "cover_letters"
        cl_dir.mkdir(parents=True, exist_ok=True)
        (cl_dir / f"cover_letter_{entry_id}.txt").write_text("Cover letter text.")


def test_list_history_empty_when_no_output_dir(client):
    c, _ = client
    resp = c.get("/api/tailor/history/rohit")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_history_returns_entry_with_metadata(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200", job_url="https://example.com/job", created_at="2026-01-01T12:00:00+00:00")
    resp = c.get("/api/tailor/history/rohit")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["id"] == "rohit_acme_20260101_1200"
    assert entry["job_url"] == "https://example.com/job"
    assert entry["created_at"] == "2026-01-01T12:00:00+00:00"
    assert entry["pdf_available"] is True
    assert entry["cover_letter_available"] is True


def test_list_history_falls_back_to_mtime_and_empty_url_without_meta(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200")
    resp = c.get("/api/tailor/history/rohit")
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["job_url"] == ""
    assert entries[0]["created_at"]  # some ISO timestamp derived from mtime


def test_list_history_reflects_missing_pdf_or_cover_letter(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200", with_pdf=False, with_cover_letter=False)
    resp = c.get("/api/tailor/history/rohit")
    entry = resp.json()[0]
    assert entry["pdf_available"] is False
    assert entry["cover_letter_available"] is False


def test_list_history_sorted_newest_first(client):
    c, root = client
    _write_run(root, "rohit", "run_a", created_at="2026-01-01T00:00:00+00:00")
    _write_run(root, "rohit", "run_b", created_at="2026-02-01T00:00:00+00:00")
    resp = c.get("/api/tailor/history/rohit")
    entries = resp.json()
    assert [e["id"] for e in entries] == ["run_b", "run_a"]


def test_list_history_rejects_path_traversal_slug(client):
    c, _ = client
    resp = c.get("/api/tailor/history/%2E%2E")
    assert resp.status_code == 400


def test_download_history_pdf(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200")
    resp = c.get("/api/tailor/history/rohit/rohit_acme_20260101_1200/pdf")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4"


def test_download_history_pdf_404_when_missing(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200", with_pdf=False)
    resp = c.get("/api/tailor/history/rohit/rohit_acme_20260101_1200/pdf")
    assert resp.status_code == 404


def test_download_history_cover_letter(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200")
    resp = c.get("/api/tailor/history/rohit/rohit_acme_20260101_1200/cover-letter")
    assert resp.status_code == 200
    assert resp.text == "Cover letter text."


def test_download_history_cover_letter_404_when_missing(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200", with_cover_letter=False)
    resp = c.get("/api/tailor/history/rohit/rohit_acme_20260101_1200/cover-letter")
    assert resp.status_code == 404


def test_download_history_rejects_invalid_entry_id(client):
    c, root = client
    _write_run(root, "rohit", "rohit_acme_20260101_1200")
    resp = c.get("/api/tailor/history/rohit/%2E%2E/pdf")
    assert resp.status_code == 400


def test_history_includes_score_and_verdict(client, monkeypatch):
    c, root = client
    import job_analysis
    monkeypatch.setattr(job_analysis, "ROOT", root)
    _write_run(root, "rohit", "run_a", job_url="https://example.com/job", created_at="2026-01-01T00:00:00+00:00")
    meta_path = root / "output" / "profiles" / "rohit" / "resumes" / "meta_run_a.json"
    meta = json.loads(meta_path.read_text())
    meta["analysis_id"] = "0123456789abcdef"
    meta_path.write_text(json.dumps(meta))
    job_analysis.save_analysis("rohit", {"analysis_id": "0123456789abcdef", "match_score": 81, "verdict": "strong fit"})

    entry = c.get("/api/tailor/history/rohit").json()[0]
    assert entry["match_score"] == 81
    assert entry["verdict"] == "strong fit"


def test_history_score_null_without_analysis(client):
    c, root = client
    _write_run(root, "rohit", "run_b", job_url="https://example.com/job")
    entry = c.get("/api/tailor/history/rohit").json()[0]
    assert entry["match_score"] is None
    assert entry["verdict"] is None
