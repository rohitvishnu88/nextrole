import json
import sys
from datetime import datetime, timedelta, timezone
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


def test_merge_job_adds_new_record():
    store = {"jobs": {}}
    candidate = {
        "source": "greenhouse", "title": "Data Engineer", "company": "Acme",
        "location": "London", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "relevance_score": 8, "match_reason": "Good fit",
    }
    job_store.merge_job(store, candidate, "2026-07-17T00:00:00")
    job_id = job_store.make_job_id(candidate["url"])
    assert store["jobs"][job_id]["status"] == "new"
    assert store["jobs"][job_id]["first_seen_at"] == "2026-07-17T00:00:00"
    assert store["jobs"][job_id]["last_seen_at"] == "2026-07-17T00:00:00"


def test_merge_job_refreshes_new_or_seen_record():
    url = "https://boards.greenhouse.io/acme/jobs/1"
    job_id = job_store.make_job_id(url)
    store = {"jobs": {job_id: {
        "id": job_id, "status": "seen", "relevance_score": 5, "match_reason": "old reason",
        "first_seen_at": "2026-07-01T00:00:00", "last_seen_at": "2026-07-01T00:00:00",
    }}}
    candidate = {"source": "greenhouse", "title": "Data Engineer", "company": "Acme",
                 "location": "London", "url": url, "relevance_score": 9, "match_reason": "new reason"}
    job_store.merge_job(store, candidate, "2026-07-17T00:00:00")
    record = store["jobs"][job_id]
    assert record["status"] == "seen"
    assert record["relevance_score"] == 9
    assert record["match_reason"] == "new reason"
    assert record["last_seen_at"] == "2026-07-17T00:00:00"
    assert record["first_seen_at"] == "2026-07-01T00:00:00"


def test_merge_job_leaves_applied_record_untouched_except_last_seen():
    url = "https://boards.greenhouse.io/acme/jobs/1"
    job_id = job_store.make_job_id(url)
    store = {"jobs": {job_id: {
        "id": job_id, "status": "applied", "relevance_score": 5, "match_reason": "old reason",
        "first_seen_at": "2026-07-01T00:00:00", "last_seen_at": "2026-07-01T00:00:00",
    }}}
    candidate = {"source": "greenhouse", "title": "Data Engineer", "company": "Acme",
                 "location": "London", "url": url, "relevance_score": 9, "match_reason": "new reason"}
    job_store.merge_job(store, candidate, "2026-07-17T00:00:00")
    record = store["jobs"][job_id]
    assert record["status"] == "applied"
    assert record["relevance_score"] == 5
    assert record["match_reason"] == "old reason"
    assert record["last_seen_at"] == "2026-07-17T00:00:00"


def test_merge_job_leaves_dismissed_record_untouched_except_last_seen():
    url = "https://boards.greenhouse.io/acme/jobs/1"
    job_id = job_store.make_job_id(url)
    store = {"jobs": {job_id: {
        "id": job_id, "status": "dismissed", "relevance_score": 5, "match_reason": "old reason",
        "first_seen_at": "2026-07-01T00:00:00", "last_seen_at": "2026-07-01T00:00:00",
    }}}
    candidate = {"source": "greenhouse", "title": "Data Engineer", "company": "Acme",
                 "location": "London", "url": url, "relevance_score": 9, "match_reason": "new reason"}
    job_store.merge_job(store, candidate, "2026-07-17T00:00:00")
    record = store["jobs"][job_id]
    assert record["status"] == "dismissed"
    assert record["relevance_score"] == 5
    assert record["match_reason"] == "old reason"
    assert record["last_seen_at"] == "2026-07-17T00:00:00"


def test_merge_job_leaves_closed_record_untouched_except_last_seen():
    url = "https://boards.greenhouse.io/acme/jobs/1"
    job_id = job_store.make_job_id(url)
    store = {"jobs": {job_id: {
        "id": job_id, "status": "closed", "relevance_score": 5, "match_reason": "old reason",
        "first_seen_at": "2026-07-01T00:00:00", "last_seen_at": "2026-07-01T00:00:00",
    }}}
    candidate = {"source": "greenhouse", "title": "Data Engineer", "company": "Acme",
                 "location": "London", "url": url, "relevance_score": 9, "match_reason": "new reason"}
    job_store.merge_job(store, candidate, "2026-07-17T00:00:00")
    record = store["jobs"][job_id]
    assert record["status"] == "closed"
    assert record["relevance_score"] == 5
    assert record["match_reason"] == "old reason"
    assert record["last_seen_at"] == "2026-07-17T00:00:00"


def test_mark_status_updates_existing_job():
    store = {"jobs": {"abc": {"id": "abc", "status": "new"}}}
    assert job_store.mark_status(store, "abc", "applied") is True
    assert store["jobs"]["abc"]["status"] == "applied"


def test_mark_status_returns_false_for_unknown_id():
    store = {"jobs": {}}
    assert job_store.mark_status(store, "missing", "applied") is False


def test_mark_new_as_seen_transitions_only_new_jobs():
    store = {"jobs": {
        "a": {"id": "a", "status": "new"},
        "b": {"id": "b", "status": "applied"},
    }}
    changed = job_store.mark_new_as_seen(store)
    assert changed is True
    assert store["jobs"]["a"]["status"] == "seen"
    assert store["jobs"]["b"]["status"] == "applied"


def test_mark_new_as_seen_returns_false_when_nothing_new():
    store = {"jobs": {"a": {"id": "a", "status": "seen"}}}
    assert job_store.mark_new_as_seen(store) is False


def test_visible_jobs_excludes_dismissed_and_closed_sorted_by_score():
    store = {"jobs": {
        "a": {"id": "a", "status": "new", "relevance_score": 5},
        "b": {"id": "b", "status": "dismissed", "relevance_score": 9},
        "c": {"id": "c", "status": "closed", "relevance_score": 9},
        "d": {"id": "d", "status": "seen", "relevance_score": 8},
    }}
    visible = job_store.visible_jobs(store)
    assert [j["id"] for j in visible] == ["d", "a"]


def test_process_search_results_adds_fresh_jobs():
    store = {"jobs": {}}
    raw_jobs = [
        {"title": "Data Engineer", "company": "Acme", "location": "London",
         "url": "https://boards.greenhouse.io/acme/jobs/1", "relevance_score": 8, "match_reason": "Good fit"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: True)
    assert len(store["jobs"]) == 1


def test_process_search_results_drops_unknown_domain():
    store = {"jobs": {}}
    raw_jobs = [
        {"title": "Data Engineer", "company": "Acme", "location": "London",
         "url": "https://example.com/careers/1", "relevance_score": 8, "match_reason": "Good fit"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: True)
    assert len(store["jobs"]) == 0


def test_process_search_results_drops_closed_jobs():
    store = {"jobs": {}}
    raw_jobs = [
        {"title": "Data Engineer", "company": "Acme", "location": "London",
         "url": "https://boards.greenhouse.io/acme/jobs/1", "relevance_score": 8, "match_reason": "Good fit"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: False)
    assert len(store["jobs"]) == 0


def test_process_search_results_drops_yc_duplicate_of_existing_store_job():
    existing_id = job_store.make_job_id("https://boards.greenhouse.io/acme/jobs/1")
    store = {"jobs": {existing_id: {
        "id": existing_id, "source": "greenhouse", "company": "Acme", "title": "Data Engineer", "status": "seen",
    }}}
    raw_jobs = [
        {"title": "Data Engineer", "company": "Acme", "location": "Remote",
         "url": "https://www.workatastartup.com/jobs/999", "relevance_score": 7, "match_reason": "Also fits"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: True)
    assert len(store["jobs"]) == 1


def test_process_search_results_drops_yc_duplicate_within_same_batch():
    store = {"jobs": {}}
    raw_jobs = [
        {"title": "Data Engineer", "company": "Acme", "location": "London",
         "url": "https://boards.greenhouse.io/acme/jobs/1", "relevance_score": 8, "match_reason": "Good fit"},
        {"title": "Data Engineer", "company": "Acme", "location": "Remote",
         "url": "https://www.workatastartup.com/jobs/999", "relevance_score": 7, "match_reason": "Also fits"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: True)
    assert len(store["jobs"]) == 1
    sources = {j["source"] for j in store["jobs"].values()}
    assert sources == {"greenhouse"}


def test_process_search_results_dedup_is_order_independent():
    store = {"jobs": {}}
    raw_jobs = [
        {"title": "Data Engineer", "company": "Acme", "location": "Remote",
         "url": "https://www.workatastartup.com/jobs/999", "relevance_score": 7, "match_reason": "Also fits"},
        {"title": "Data Engineer", "company": "Acme", "location": "London",
         "url": "https://boards.greenhouse.io/acme/jobs/1", "relevance_score": 8, "match_reason": "Good fit"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: True)
    assert len(store["jobs"]) == 1
    sources = {j["source"] for j in store["jobs"].values()}
    assert sources == {"greenhouse"}


def test_process_search_results_skips_job_missing_title():
    store = {"jobs": {}}
    raw_jobs = [
        {"company": "Acme", "location": "London",
         "url": "https://boards.greenhouse.io/acme/jobs/1", "relevance_score": 8, "match_reason": "Good fit"},
    ]
    job_store.process_search_results(raw_jobs, store, "2026-07-17T00:00:00", verify_open=lambda url: True)
    assert len(store["jobs"]) == 0


def test_reverify_stale_jobs_marks_closed_when_verify_fails():
    now = datetime.now(timezone.utc)
    stale = (now - timedelta(hours=25)).isoformat()
    store = {"jobs": {"a": {
        "id": "a", "status": "new", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "last_verified_at": stale,
    }}}
    job_store.reverify_stale_jobs(store, now, verify_open=lambda url: False)
    assert store["jobs"]["a"]["status"] == "closed"


def test_reverify_stale_jobs_skips_recently_verified():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=2)).isoformat()
    store = {"jobs": {"a": {
        "id": "a", "status": "new", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "last_verified_at": recent,
    }}}
    calls = []
    job_store.reverify_stale_jobs(store, now, verify_open=lambda url: calls.append(url) or True)
    assert calls == []
    assert store["jobs"]["a"]["status"] == "new"


def test_reverify_stale_jobs_skips_applied_and_dismissed():
    now = datetime.now(timezone.utc)
    store = {"jobs": {
        "a": {"id": "a", "status": "applied", "url": "https://x.com/1", "last_verified_at": ""},
        "b": {"id": "b", "status": "dismissed", "url": "https://x.com/2", "last_verified_at": ""},
    }}
    calls = []
    job_store.reverify_stale_jobs(store, now, verify_open=lambda url: calls.append(url) or True)
    assert calls == []


def test_build_feedback_summary_empty_store_returns_empty_string():
    store = {"jobs": {}}
    assert job_store.build_feedback_summary(store) == ""


def test_build_feedback_summary_includes_applied_and_dismissed():
    store = {"jobs": {
        "a": {"title": "Data Engineer", "company": "Acme", "status": "applied", "last_seen_at": "2026-07-01T00:00:00"},
        "b": {"title": "QA Engineer", "company": "Beta", "status": "dismissed", "last_seen_at": "2026-07-02T00:00:00"},
    }}
    summary = job_store.build_feedback_summary(store)
    assert "Applied to" in summary
    assert "Data Engineer @ Acme" in summary
    assert "Dismissed" in summary
    assert "QA Engineer @ Beta" in summary


def test_build_feedback_summary_caps_at_n_most_recent():
    jobs = {}
    for i in range(15):
        jobs[str(i)] = {
            "title": f"Role {i}", "company": "Acme", "status": "dismissed",
            "last_seen_at": f"2026-07-{i+1:02d}T00:00:00",
        }
    store = {"jobs": jobs}
    summary = job_store.build_feedback_summary(store, n=10)
    assert "Role 14" in summary
    assert "Role 0" not in summary
