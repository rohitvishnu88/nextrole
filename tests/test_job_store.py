import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import job_store


def test_profile_jobs_path_per_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    path = job_store.profile_jobs_path("rohit")
    assert path == tmp_path / "profiles" / "rohit" / "jobs.json"


def test_profile_jobs_path_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    path = job_store.profile_jobs_path("")
    assert path == tmp_path / "jobs" / "jobs.json"


def test_load_store_missing_file_returns_empty_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    store = job_store.load_store("rohit")
    assert store == {"generated_at": "", "candidate": "", "jobs": {}}


def test_load_store_migrates_legacy_list_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    legacy_path = job_store.profile_jobs_path("")
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_text(json.dumps({
        "generated_at": "2026-01-01T00:00:00",
        "candidate": "Old Shape",
        "total_jobs": 1,
        "new_jobs": 1,
        "jobs": [{"title": "Old Job", "url": "https://linkedin.com/jobs/view/1"}],
    }))
    store = job_store.load_store("")
    assert store["jobs"] == {}
    assert store["candidate"] == "Old Shape"


def test_save_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    store = {"generated_at": "2026-07-17T00:00:00", "candidate": "Test", "jobs": {"abc123": {"id": "abc123"}}}
    job_store.save_store("rohit", store)
    assert job_store.load_store("rohit") == store


def test_profile_jobs_path_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        job_store.profile_jobs_path("../../../../tmp/evil")


def test_profile_jobs_path_rejects_slash(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        job_store.profile_jobs_path("rohit/evil")


def test_profile_jobs_path_accepts_valid_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    path = job_store.profile_jobs_path("rohit-vishnu-2")
    assert path == tmp_path / "profiles" / "rohit-vishnu-2" / "jobs.json"


def test_load_store_fills_missing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    path = job_store.profile_jobs_path("rohit")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"jobs": {"abc": {"id": "abc"}}}))
    store = job_store.load_store("rohit")
    assert store == {"generated_at": "", "candidate": "", "jobs": {"abc": {"id": "abc"}}}


def test_load_store_handles_bare_list_top_level(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path))
    path = job_store.profile_jobs_path("rohit")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"title": "Old Job"}]))
    store = job_store.load_store("rohit")
    assert store == {"generated_at": "", "candidate": "", "jobs": {}}


def test_make_job_id_is_stable_and_short():
    id1 = job_store.make_job_id("https://boards.greenhouse.io/acme/jobs/12345")
    id2 = job_store.make_job_id("https://boards.greenhouse.io/acme/jobs/12345")
    assert id1 == id2
    assert len(id1) == 12


def test_make_job_id_differs_for_different_urls():
    id1 = job_store.make_job_id("https://boards.greenhouse.io/acme/jobs/12345")
    id2 = job_store.make_job_id("https://boards.greenhouse.io/acme/jobs/67890")
    assert id1 != id2


def test_derive_source_greenhouse():
    assert job_store.derive_source("https://boards.greenhouse.io/acme/jobs/1") == "greenhouse"


def test_derive_source_lever():
    assert job_store.derive_source("https://jobs.lever.co/acme/abc-123") == "lever"


def test_derive_source_yc():
    assert job_store.derive_source("https://www.workatastartup.com/jobs/12345") == "yc"


def test_derive_source_linkedin():
    assert job_store.derive_source("https://www.linkedin.com/jobs/view/12345") == "linkedin"


def test_derive_source_other():
    assert job_store.derive_source("https://example.com/careers/1") == "other"


def test_derive_source_rejects_lookalike_domain():
    assert job_store.derive_source("https://clever.co/jobs/1") == "other"
    assert job_store.derive_source("https://linkedin.com.evil.com/phish") == "other"


def test_normalize_dedup_key_case_and_whitespace_insensitive():
    key1 = job_store.normalize_dedup_key("Acme Corp", "Senior Data Engineer")
    key2 = job_store.normalize_dedup_key("  acme corp  ", "senior   data engineer")
    assert key1 == key2


def test_is_cross_source_duplicate_true_when_other_source_matches():
    candidate = {"source": "yc", "company": "Acme", "title": "Data Engineer"}
    existing = {
        "abc": {"source": "greenhouse", "company": "Acme", "title": "Data Engineer"},
    }
    assert job_store.is_cross_source_duplicate(candidate, existing) is True


def test_is_cross_source_duplicate_false_when_no_match():
    candidate = {"source": "yc", "company": "Acme", "title": "Data Engineer"}
    existing = {
        "abc": {"source": "greenhouse", "company": "Acme", "title": "Product Manager"},
    }
    assert job_store.is_cross_source_duplicate(candidate, existing) is False


def test_is_cross_source_duplicate_false_when_candidate_not_yc():
    candidate = {"source": "linkedin", "company": "Acme", "title": "Data Engineer"}
    existing = {
        "abc": {"source": "greenhouse", "company": "Acme", "title": "Data Engineer"},
    }
    assert job_store.is_cross_source_duplicate(candidate, existing) is False


def test_is_cross_source_duplicate_ignores_other_yc_records():
    candidate = {"source": "yc", "company": "Acme", "title": "Data Engineer"}
    existing = {
        "abc": {"source": "yc", "company": "Acme", "title": "Data Engineer"},
    }
    assert job_store.is_cross_source_duplicate(candidate, existing) is False
