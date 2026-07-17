# Job Search UI + Multi-Source ATS Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen job search from LinkedIn-only to LinkedIn + Greenhouse + Lever + a supplementary Y Combinator source, make results and a "Search now" trigger available in the web UI with a persistent apply/dismiss list, verify posting freshness, and add a one-click path from a job match into the existing Tailor flow.

**Architecture:** Two new pure-logic Python modules (`agents/job_store.py` for persistence/merge/dedup, `agents/job_freshness.py` for closure detection) sit underneath the existing `agents/job_search_agent.py` orchestration, which now writes to a per-profile persistent store instead of three global overwrite files. A new FastAPI router (`a2a/routes/job_search.py`) follows the existing background-task + polling convention from `search_brief.py`. The frontend gets one new page (`web/app/jobs/page.tsx`) plus a `JobCard` component, wired into `TopNav.tsx` and reusing the existing `/api/tailor` endpoint for the Tailor button.

**Tech Stack:** Python 3.9, FastAPI, pytest, httpx (already a dependency) for freshness checks, Next.js/TypeScript/Tailwind for the frontend.

**Spec:** `docs/superpowers/specs/2026-07-17-job-search-ui-ats-design.md`

---

## Compatibility constraints discovered during planning

Two existing call sites must keep working, found by grepping for all callers of `job_search_agent` before touching it:

1. **`agents/main_agent.py`** (real CLI, not dead code) calls `job_search_agent.run(resume, include_seen=args.include_seen, profile_slug=profile_slug)` and `job_search_agent.mark_applied(args.applied)`. `include_seen` is kept as a real parameter (not removed) — it now means "return everything visible in the store, not just this run's newly-found jobs." `mark_applied` gains a `profile_slug` parameter; `main_agent.py`'s one call site is updated to pass it (Task 12).
2. **`a2a/skills/job_search.py`** (the A2A chat endpoint) calls `job_search_agent.run(resume, include_seen=False)` with no `profile_slug` — it stays on the legacy global path by design (empty-slug fallback in `job_store.profile_jobs_path`, Task 1). Only its `include_seen=False` keyword is dropped since the parameter itself isn't removed, so actually **no change needed there** — confirmed by keeping `include_seen` in the signature (see Task 12).
3. **`tests/test_job_search.py`** is a pre-existing broken script (calls `json.load(open('data/resume_data.json'))`, which doesn't exist — it already errors during pytest collection today). It's superseded by the new tests in Tasks 1–10 and is deleted in Task 15.
4. The legacy `output/jobs/jobs.json` (still on disk from before this feature) has the OLD shape — `jobs` is a **list**, not the new dict-of-records shape. `job_store.load_store` must detect and reset this rather than crash (Task 1).

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `agents/job_store.py` | Create | Persistent store: paths, load/save, id/source derivation, dedup, merge, status transitions, feedback summary. Pure logic — no network calls. |
| `agents/job_freshness.py` | Create | Closure detection: URL parsing for Greenhouse/Lever, closure-phrase heuristic, re-verify cadence, the two direct API checks (network). |
| `agents/job_search_agent.py` | Modify | Orchestration: 4-domain search loop, wires `job_store`/`job_freshness` together, `run()` and `mark_applied()`. |
| `agents/main_agent.py` | Modify (1 line) | Pass `profile_slug` to `mark_applied`. |
| `a2a/skills/job_search.py` | No change | Confirmed compatible — see constraints above. |
| `a2a/routes/job_search.py` | Create | REST endpoints: trigger search, list/poll, apply, dismiss. |
| `a2a/server.py` | Modify (2 lines) | Register the new router. |
| `tests/test_job_store.py` | Create | Unit tests for all `job_store` functions. |
| `tests/test_job_freshness.py` | Create | Unit tests for all `job_freshness` pure functions. |
| `tests/test_job_search_api.py` | Create | Route tests, monkeypatching `job_search_agent.run`. |
| `tests/test_job_search.py` | Delete | Superseded, already broken. |
| `web/lib/types.ts` | Modify | Add `JobMatch`, `JobSource` types. |
| `web/lib/api.ts` | Modify | Add `searchJobs`, `getJobMatches`, `applyToJob`, `dismissJob`. |
| `web/components/JobCard.tsx` | Create | One job's card UI: badge, actions (View/Tailor/Applied/Dismiss). |
| `web/app/jobs/page.tsx` | Create | Jobs page: header, Search now button, list. |
| `web/components/TopNav.tsx` | Modify (2 lines) | Add "Jobs" nav entry. |
| `web/app/tailor/page.tsx` | Modify | Resume-polling fix for jobs launched from the Jobs page. |

---

## Task 1: `job_store.py` — paths, load/save, legacy-shape guard

**Files:**
- Create: `agents/job_store.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_job_store.py
import json
import sys
from pathlib import Path

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_store'`

- [ ] **Step 3: Write the implementation**

```python
# agents/job_store.py
"""Persistent per-profile job-match store: paths, merge, dedup, status, feedback summary."""
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent


def _output_dir() -> Path:
    base = os.environ.get("JOBS_OUTPUT_DIR", str(ROOT / "output"))
    return Path(base)


def profile_jobs_path(profile_slug: str) -> Path:
    if not profile_slug:
        return _output_dir() / "jobs" / "jobs.json"
    return _output_dir() / "profiles" / profile_slug / "jobs.json"


def load_store(profile_slug: str) -> dict:
    path = profile_jobs_path(profile_slug)
    if not path.exists():
        return {"generated_at": "", "candidate": "", "jobs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("jobs"), dict):
        data["jobs"] = {}
    return data


def save_store(profile_slug: str, store: dict) -> None:
    path = profile_jobs_path(profile_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_store.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/job_store.py tests/test_job_store.py
git commit -m "feat: add per-profile job store with legacy-shape migration guard"
```

---

## Task 2: `job_store.py` — job id and source derivation

**Files:**
- Modify: `agents/job_store.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_job_store.py

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_store.py -v -k "make_job_id or derive_source"`
Expected: FAIL with `AttributeError: module 'job_store' has no attribute 'make_job_id'`

- [ ] **Step 3: Write the implementation**

```python
# Append to agents/job_store.py

def make_job_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def derive_source(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "workatastartup.com" in host:
        return "yc"
    if "linkedin.com" in host:
        return "linkedin"
    return "other"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_store.py -v -k "make_job_id or derive_source"`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/job_store.py tests/test_job_store.py
git commit -m "feat: add job id hashing and source domain derivation"
```

---

## Task 3: `job_store.py` — cross-source dedup

**Files:**
- Modify: `agents/job_store.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_job_store.py

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_store.py -v -k "dedup or normalize"`
Expected: FAIL with `AttributeError: module 'job_store' has no attribute 'normalize_dedup_key'`

- [ ] **Step 3: Write the implementation**

```python
# Append to agents/job_store.py

def normalize_dedup_key(company: str, title: str) -> str:
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())
    return f"{norm(company)}::{norm(title)}"


def is_cross_source_duplicate(candidate: dict, existing_jobs: dict) -> bool:
    if candidate.get("source") != "yc":
        return False
    key = normalize_dedup_key(candidate.get("company", ""), candidate.get("title", ""))
    for job in existing_jobs.values():
        if job.get("source") == "yc":
            continue
        if normalize_dedup_key(job.get("company", ""), job.get("title", "")) == key:
            return True
    return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_store.py -v -k "dedup or normalize"`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/job_store.py tests/test_job_store.py
git commit -m "feat: add cross-source dedup so YC never duplicates a role found elsewhere"
```

---

## Task 4: `job_store.py` — merge_job and status helpers

**Files:**
- Modify: `agents/job_store.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_job_store.py

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_store.py -v -k "merge_job or mark_status or mark_new_as_seen or visible_jobs"`
Expected: FAIL with `AttributeError: module 'job_store' has no attribute 'merge_job'`

- [ ] **Step 3: Write the implementation**

```python
# Append to agents/job_store.py

def merge_job(store: dict, candidate: dict, now_iso: str) -> None:
    jobs = store.setdefault("jobs", {})
    job_id = make_job_id(candidate["url"])
    existing = jobs.get(job_id)
    if existing is None:
        jobs[job_id] = {
            "id": job_id,
            "source": candidate["source"],
            "title": candidate["title"],
            "company": candidate["company"],
            "location": candidate.get("location", ""),
            "url": candidate["url"],
            "relevance_score": candidate.get("relevance_score", 0),
            "match_reason": candidate.get("match_reason", ""),
            "status": "new",
            "first_seen_at": now_iso,
            "last_seen_at": now_iso,
            "last_verified_at": now_iso,
        }
        return
    existing["last_seen_at"] = now_iso
    if existing["status"] in ("new", "seen"):
        existing["relevance_score"] = candidate.get("relevance_score", existing["relevance_score"])
        existing["match_reason"] = candidate.get("match_reason", existing["match_reason"])


def mark_status(store: dict, job_id: str, status: str) -> bool:
    job = store.get("jobs", {}).get(job_id)
    if job is None:
        return False
    job["status"] = status
    return True


def mark_new_as_seen(store: dict) -> bool:
    changed = False
    for job in store.get("jobs", {}).values():
        if job.get("status") == "new":
            job["status"] = "seen"
            changed = True
    return changed


def visible_jobs(store: dict) -> list:
    jobs = [j for j in store.get("jobs", {}).values() if j.get("status") not in ("dismissed", "closed")]
    return sorted(jobs, key=lambda j: j.get("relevance_score", 0), reverse=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_store.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add agents/job_store.py tests/test_job_store.py
git commit -m "feat: add job store merge, status transitions, and visible-jobs listing"
```

---

## Task 5: `job_freshness.py` — closure heuristic and re-verify cadence

**Files:**
- Create: `agents/job_freshness.py`
- Test: `tests/test_job_freshness.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_job_freshness.py
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
import job_freshness


def test_looks_closed_detects_linkedin_phrase():
    text = "Senior Data Engineer at Acme. No longer accepting applications."
    assert job_freshness.looks_closed(text) is True


def test_looks_closed_detects_filled_phrase():
    assert job_freshness.looks_closed("This position has been filled.") is True


def test_looks_closed_false_for_normal_listing():
    text = "Senior Data Engineer at Acme. Apply now. We are hiring across the UK."
    assert job_freshness.looks_closed(text) is False


def test_looks_closed_case_insensitive():
    assert job_freshness.looks_closed("NO LONGER ACCEPTING APPLICATIONS") is True


def test_needs_reverify_true_when_never_verified():
    assert job_freshness.needs_reverify("", datetime.now(timezone.utc)) is True


def test_needs_reverify_false_within_24h():
    now = datetime.now(timezone.utc)
    last = (now - timedelta(hours=2)).isoformat()
    assert job_freshness.needs_reverify(last, now) is False


def test_needs_reverify_true_after_24h():
    now = datetime.now(timezone.utc)
    last = (now - timedelta(hours=25)).isoformat()
    assert job_freshness.needs_reverify(last, now) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_freshness.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_freshness'`

- [ ] **Step 3: Write the implementation**

```python
# agents/job_freshness.py
"""Freshness verification for job postings: closure detection and re-verify cadence."""
from datetime import datetime, timedelta

REVERIFY_INTERVAL = timedelta(hours=24)

CLOSURE_PHRASES = (
    "no longer accepting applications",
    "this position has been filled",
    "this job posting is no longer active",
    "position is no longer available",
)


def looks_closed(page_text: str) -> bool:
    lowered = page_text.lower()
    return any(phrase in lowered for phrase in CLOSURE_PHRASES)


def needs_reverify(last_verified_at_iso: str, now: datetime) -> bool:
    if not last_verified_at_iso:
        return True
    last_verified = datetime.fromisoformat(last_verified_at_iso)
    return now - last_verified >= REVERIFY_INTERVAL
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_freshness.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/job_freshness.py tests/test_job_freshness.py
git commit -m "feat: add closure-phrase heuristic and 24h re-verify cadence"
```

---

## Task 6: `job_freshness.py` — Greenhouse/Lever URL parsing and API checks

**Files:**
- Modify: `agents/job_freshness.py`
- Test: `tests/test_job_freshness.py`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_job_freshness.py

def test_parse_greenhouse_extracts_company_and_id():
    url = "https://boards.greenhouse.io/acme/jobs/4567890"
    assert job_freshness.parse_greenhouse(url) == ("acme", "4567890")


def test_parse_greenhouse_returns_none_for_non_matching_url():
    assert job_freshness.parse_greenhouse("https://boards.greenhouse.io/acme/about") is None


def test_parse_lever_extracts_company_and_id():
    url = "https://jobs.lever.co/acme/1a2b3c4d-5e6f-7890-abcd-ef1234567890"
    assert job_freshness.parse_lever(url) == ("acme", "1a2b3c4d-5e6f-7890-abcd-ef1234567890")


def test_parse_lever_returns_none_for_non_matching_url():
    assert job_freshness.parse_lever("https://jobs.lever.co/acme") is None


def test_check_greenhouse_open_true_on_200(monkeypatch):
    class FakeResponse:
        status_code = 200

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr(job_freshness.httpx, "get", fake_get)
    assert job_freshness.check_greenhouse_open("acme", "123") is True


def test_check_greenhouse_open_false_on_404(monkeypatch):
    class FakeResponse:
        status_code = 404

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr(job_freshness.httpx, "get", fake_get)
    assert job_freshness.check_greenhouse_open("acme", "123") is False


def test_check_lever_open_true_on_200(monkeypatch):
    class FakeResponse:
        status_code = 200

    def fake_get(url, timeout):
        return FakeResponse()

    monkeypatch.setattr(job_freshness.httpx, "get", fake_get)
    assert job_freshness.check_lever_open("acme", "abc") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_freshness.py -v -k "parse_ or check_"`
Expected: FAIL with `AttributeError: module 'job_freshness' has no attribute 'parse_greenhouse'`

- [ ] **Step 3: Write the implementation**

```python
# Add near the top of agents/job_freshness.py, after the existing imports
import re

import httpx

# Append to agents/job_freshness.py

def parse_greenhouse(url: str):
    match = re.search(r"boards\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if not match:
        return None
    return match.group(1), match.group(2)


def parse_lever(url: str):
    match = re.search(r"jobs\.lever\.co/([^/]+)/([0-9a-fA-F-]+)", url)
    if not match:
        return None
    return match.group(1), match.group(2)


def check_greenhouse_open(company: str, posting_id: str) -> bool:
    resp = httpx.get(
        f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{posting_id}",
        timeout=10,
    )
    return resp.status_code == 200


def check_lever_open(company: str, posting_id: str) -> bool:
    resp = httpx.get(f"https://api.lever.co/v0/postings/{company}/{posting_id}", timeout=10)
    return resp.status_code == 200
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_freshness.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add agents/job_freshness.py tests/test_job_freshness.py
git commit -m "feat: add Greenhouse/Lever URL parsing and public API freshness checks"
```

---

## Task 7: `job_store.py` — process_search_results (discovery-time filter/dedup/verify/merge)

**Files:**
- Modify: `agents/job_store.py`
- Test: `tests/test_job_store.py`

This is the pipeline that turns a batch of freshly-found raw jobs into store entries: derive source, drop unknown domains, drop cross-source duplicates, verify still open, merge. `verify_open` is injected so this stays testable without network calls — real wiring happens in Task 12.

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_job_store.py

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_store.py -v -k process_search_results`
Expected: FAIL with `AttributeError: module 'job_store' has no attribute 'process_search_results'`

- [ ] **Step 3: Write the implementation**

```python
# Append to agents/job_store.py

def process_search_results(raw_jobs: list, store: dict, now_iso: str, verify_open) -> None:
    kept = []
    for raw in raw_jobs:
        job = dict(raw)
        job["source"] = derive_source(job.get("url", ""))
        if job["source"] == "other":
            continue
        combined = dict(store.get("jobs", {}))
        combined.update({f"_pending_{i}": j for i, j in enumerate(kept)})
        if is_cross_source_duplicate(job, combined):
            continue
        if not verify_open(job["url"]):
            continue
        kept.append(job)
    for job in kept:
        merge_job(store, job, now_iso)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_store.py -v`
Expected: PASS (all tests so far)

- [ ] **Step 5: Commit**

```bash
git add agents/job_store.py tests/test_job_store.py
git commit -m "feat: add process_search_results pipeline (filter, dedup, verify, merge)"
```

---

## Task 8: `job_store.py` — reverify_stale_jobs and build_feedback_summary

**Files:**
- Modify: `agents/job_store.py`
- Test: `tests/test_job_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# Append to tests/test_job_store.py
from datetime import datetime, timedelta, timezone


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_store.py -v -k "reverify_stale_jobs or build_feedback_summary"`
Expected: FAIL with `AttributeError: module 'job_store' has no attribute 'reverify_stale_jobs'`

- [ ] **Step 3: Write the implementation**

```python
# Add near the top of agents/job_store.py, after the existing imports
import sys
sys.path.insert(0, str(Path(__file__).parent))
import job_freshness

# Append to agents/job_store.py

def reverify_stale_jobs(store: dict, now, verify_open) -> None:
    for job in store.get("jobs", {}).values():
        if job.get("status") not in ("new", "seen"):
            continue
        if not job_freshness.needs_reverify(job.get("last_verified_at", ""), now):
            continue
        job["last_verified_at"] = now.isoformat()
        if not verify_open(job["url"]):
            job["status"] = "closed"


def build_feedback_summary(store: dict, n: int = 10) -> str:
    jobs = list(store.get("jobs", {}).values())
    applied = sorted(
        [j for j in jobs if j.get("status") == "applied"],
        key=lambda j: j.get("last_seen_at", ""), reverse=True,
    )[:n]
    dismissed = sorted(
        [j for j in jobs if j.get("status") == "dismissed"],
        key=lambda j: j.get("last_seen_at", ""), reverse=True,
    )[:n]
    if not applied and not dismissed:
        return ""
    lines = ["Recent signal from past search runs:"]
    if applied:
        lines.append(
            "Applied to (positive signal — find more like these): "
            + ", ".join(f"{j['title']} @ {j['company']}" for j in applied)
        )
    if dismissed:
        lines.append(
            "Dismissed (negative signal — avoid these patterns): "
            + ", ".join(f"{j['title']} @ {j['company']}" for j in dismissed)
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_store.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add agents/job_store.py tests/test_job_store.py
git commit -m "feat: add periodic re-verification and applied/dismissed feedback summary"
```

---

## Task 9: Full `job_store.py`/`job_freshness.py` test run

**Files:** none (verification checkpoint)

- [ ] **Step 1: Run the complete new test files together**

Run: `python3 -m pytest tests/test_job_store.py tests/test_job_freshness.py -v`
Expected: PASS, all tests green, no import errors between the two modules

- [ ] **Step 2: Commit (only if any fixups were needed in Step 1)**

```bash
git add agents/job_store.py agents/job_freshness.py tests/test_job_store.py tests/test_job_freshness.py
git commit -m "fix: resolve any cross-module issues between job_store and job_freshness"
```

---

## Task 10: `agents/job_search_agent.py` — four-domain search + prompt updates

**Files:**
- Modify: `agents/job_search_agent.py:1-33` (imports/constants), `:178-249` (tools + system prompt)

No unit test for this task — it's prompt text and a tool schema, not testable logic. Verified by inspection and later by the manual smoke test in Task 16.

- [ ] **Step 1: Update imports and remove now-unused module-level file constants**

In `agents/job_search_agent.py`, replace:

```python
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL, extract_json_array

ROOT = Path(__file__).parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"
JOBS_FILE = ROOT / "output" / "jobs" / "jobs.json"
SEEN_FILE = ROOT / "output" / "jobs" / "seen_jobs.json"
APPLIED_FILE = ROOT / "output" / "jobs" / "applied_jobs.json"
MODEL = DEFAULT_MODEL
MAX_RESULTS_PER_QUERY = 5
# LinkedIn date filter param: r432000 = past 5 days
LINKEDIN_DATE_FILTER = "f_TPR=r432000"
```

with:

```python
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL, extract_json_array

sys.path.insert(0, str(Path(__file__).parent))
import job_store
import job_freshness

ROOT = Path(__file__).parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"
MODEL = DEFAULT_MODEL
MAX_RESULTS_PER_QUERY = 5
SEARCH_DOMAINS = ["linkedin.com", "boards.greenhouse.io", "jobs.lever.co", "workatastartup.com"]
```

(`JOBS_FILE`/`SEEN_FILE`/`APPLIED_FILE` are replaced by `job_store.profile_jobs_path()`; `LINKEDIN_DATE_FILTER` was already unused dead code before this change.)

- [ ] **Step 2: Replace the tool definition**

Replace the `search_linkedin_jobs` tool entry (lines ~178–194) with:

```python
    tools = [
        {
            "name": "search_job_boards",
            "description": (
                "Search LinkedIn, Greenhouse, Lever, or Y Combinator's workatastartup.com "
                "for job listings. Returns title, company, location, URL, snippet."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query including a site: filter, e.g. "
                            "'site:boards.greenhouse.io Data Engineer'"
                        )
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "read_job_page",
            "description": (
                "Fetch the full content of a job listing URL to get the complete "
                "job description before scoring it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full job listing URL"
                    }
                },
                "required": ["url"]
            }
        }
    ]
```

- [ ] **Step 3: Replace the system prompt**

Replace the `system_prompt` string (lines ~214–249) with:

```python
    system_prompt = """You are a job search agent. Find jobs posted in the last 5 days that match the candidate's profile.

Process:
1. Run up to 16 searches across four sources — no more. Mix role titles and skill angles:
   a. site:linkedin.com/jobs/view <role> <skills> UK
   b. site:boards.greenhouse.io <role> <skills>
   c. site:jobs.lever.co <role> <skills>
   d. site:workatastartup.com <role> <skills> — treat this source as SUPPLEMENTARY: only worth
      searching if the other three sources haven't already covered a role/skill angle well.
2. Role angles to cover: Solution Architect, Integration Architect, API Architect, Data Architect, Senior/Lead/Principal Data Engineer, Data Platform Engineer.
3. Skill angles to cover: MuleSoft, Apigee, Kafka, Apache Iceberg, Databricks, Snowflake, AWS data platform, Azure data platform, event-driven architecture, API management.
4. After searching, stop. Read the top 8 job pages then score everything.
5. Only include jobs from linkedin.com, boards.greenhouse.io, jobs.lever.co, or workatastartup.com — discard any other domain.
6. Discard any job posted more than 5 days ago.

Scoring rubric (1-10):
- 9-10: Exact fit. Architect or Senior/Lead/Principal Engineer title. Core tech matches (Iceberg, Kafka, MuleSoft, Apigee, AWS, or API management). UK-based.
- 7-8: Strong fit. Right seniority and domain. Transferable tech stack: Databricks, Delta Lake, Azure Data Factory, Synapse, dbt, Snowflake, Azure APIM, AWS API Gateway, IBM App Connect, Boomi. Candidate covers these without significant reskilling.
- 6: Transferable fit. Right level, overlapping domain, different but learnable stack.
- 1-5: Drop.

HARD DISCARD rules — drop immediately without scoring:
- Any title with: Junior, Mid-level, Graduate, Associate, Entry-level, Intern
- Any role outside UK (no US, EU, APAC unless explicitly remote-global)
- Any role posted more than 5 days ago
- Any domain other than linkedin.com, boards.greenhouse.io, jobs.lever.co, workatastartup.com
- Pure front-end, DevOps-only, or QA-only roles with no architecture/data/integration component

Return ONLY a JSON array, no other text:
[
  {
    "title": "Job title",
    "company": "Company name",
    "location": "Location",
    "url": "Job listing URL",
    "relevance_score": 8,
    "match_reason": "One sentence on why this fits — mention specific matching skills or experience"
  }
]"""
```

- [ ] **Step 4: Update the tool-loop's search handler to use the new tool name and domain list**

In the `while True:` loop, replace:

```python
                if block.name == "search_linkedin_jobs":
                    query = block.input["query"]
                    print(f"  Searching: {query}")
                    try:
                        results = tavily_client.search(
                            query=query,
                            max_results=MAX_RESULTS_PER_QUERY,
                            search_depth="advanced",
                            include_domains=["linkedin.com"],
                        )
                        hits = results.get("results", [])
                        # Hard filter: LinkedIn jobs only
                        hits = [
                            r for r in hits
                            if "linkedin.com/jobs" in r.get("url", "")
                        ]
```

with:

```python
                if block.name == "search_job_boards":
                    query = block.input["query"]
                    print(f"  Searching: {query}")
                    try:
                        results = tavily_client.search(
                            query=query,
                            max_results=MAX_RESULTS_PER_QUERY,
                            search_depth="advanced",
                            include_domains=SEARCH_DOMAINS,
                        )
                        hits = results.get("results", [])
                        hits = [
                            r for r in hits
                            if job_store.derive_source(r.get("url", "")) != "other"
                        ]
```

- [ ] **Step 5: Verify by inspection**

Run: `python3 -c "import sys; sys.path.insert(0, 'agents'); import job_search_agent; print('OK')"`
Expected: `OK` (module imports without syntax errors)

- [ ] **Step 6: Commit**

```bash
git add agents/job_search_agent.py
git commit -m "feat: widen job search tool to four domains (LinkedIn, Greenhouse, Lever, YC)"
```

---

## Task 11: `agents/job_search_agent.py` — feedback summary in profile prompt

**Files:**
- Modify: `agents/job_search_agent.py:48-97` (`build_profile_summary`)

- [ ] **Step 1: Insert the feedback summary into the search-brief branch of `build_profile_summary`**

Find this block near the end of the search-brief branch (the one starting `if brief_path and brief_path.exists():`):

```python
        return f"""Candidate: {name}
Seniority target: {", ".join(seniority) if seniority else "Senior/Principal"}
Current role: {current_title} at {current_company}
Summary: {summary}

Target roles (search for any of these): {", ".join(roles) if roles else "Solution Architect, Senior Data Engineer"}

Core skills to match:
{chr(10).join(f"  - {s}" for s in skills) if skills else skills_section}

Target locations: {", ".join(locations) if locations else "UK only"}
Target industries: {", ".join(industries) if industries else "any industry"}

Hard exclusions (never match):
{chr(10).join(f"  - {e}" for e in excludes) if excludes else "  - Junior, Graduate, Associate, Entry-level"}

Additional context:
{skills_section}

Hard requirements:
- Posted within the last 5 days. Discard anything older.
- LinkedIn jobs only."""
```

Replace the final two lines and the closing `"""` with:

```python
        feedback_summary = job_store.build_feedback_summary(job_store.load_store(profile_slug))

        return f"""Candidate: {name}
Seniority target: {", ".join(seniority) if seniority else "Senior/Principal"}
Current role: {current_title} at {current_company}
Summary: {summary}

Target roles (search for any of these): {", ".join(roles) if roles else "Solution Architect, Senior Data Engineer"}

Core skills to match:
{chr(10).join(f"  - {s}" for s in skills) if skills else skills_section}

Target locations: {", ".join(locations) if locations else "UK only"}
Target industries: {", ".join(industries) if industries else "any industry"}

Hard exclusions (never match):
{chr(10).join(f"  - {e}" for e in excludes) if excludes else "  - Junior, Graduate, Associate, Entry-level"}

Additional context:
{skills_section}

Hard requirements:
- Posted within the last 5 days. Discard anything older.
- Jobs from LinkedIn, Greenhouse, Lever, or workatastartup.com only.
{f"{chr(10)}{feedback_summary}" if feedback_summary else ""}"""
```

- [ ] **Step 2: Verify by manual inspection with a fixture**

Run:
```bash
python3 -c "
import sys, json
sys.path.insert(0, 'agents')
import job_search_agent, job_store

resume = {'name': 'Test User', 'summary': 'Data engineer', 'skills': {}, 'experience': []}
print(job_search_agent.build_profile_summary(resume, profile_slug=''))
"
```
Expected: prints a profile summary ending in the 'Hard requirements' block, with no feedback section (empty store) — confirms the conditional doesn't print an empty "Recent signal" header when there's no history.

- [ ] **Step 3: Commit**

```bash
git add agents/job_search_agent.py
git commit -m "feat: fold applied/dismissed feedback summary into search profile prompt"
```

---

## Task 12: `agents/job_search_agent.py` — rewire run() and mark_applied() to the new store

**Files:**
- Modify: `agents/job_search_agent.py:170` (signature), `:280-392` (loop tail + `mark_applied`)
- Modify: `agents/main_agent.py:126` (pass `profile_slug` to `mark_applied`)

This is the integration task — the pure logic (Tasks 1–8) is already tested; this wires it to the real Tavily/Anthropic clients.

- [ ] **Step 1: Update the `run()` signature**

Replace:

```python
def run(resume: dict, include_seen: bool = False, profile_slug: str = "") -> dict:
```

with (unchanged — confirming `include_seen` and `profile_slug` both stay, per the compatibility constraints above):

```python
def run(resume: dict, include_seen: bool = False, profile_slug: str = "") -> dict:
```

(No change needed to the signature itself — noting this explicitly so the next step's diff is unambiguous about what *is* changing.)

- [ ] **Step 2: Remove the now-dead `load_json`/`save_json` helpers**

These two module-level functions (originally added only to read/write `JOBS_FILE`/`SEEN_FILE`/`APPLIED_FILE`) have no remaining call sites once Steps 3–4 below land — `job_store` owns all persistence now. Delete:

```python
def load_json(path, default):
    if Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 3: Remove the old seen/applied loading and replace with the store**

Replace:

```python
    seen_urls: set = set(load_json(SEEN_FILE, []))
    applied_urls: set = set(load_json(APPLIED_FILE, []))
    profile = build_profile_summary(resume, profile_slug)
```

with:

```python
    profile = build_profile_summary(resume, profile_slug)
```

- [ ] **Step 4: Replace the tail-end of `run()` (from "# Filter applied jobs" to the final `return output`)**

Replace:

```python
    # Filter applied jobs
    all_jobs = [j for j in all_jobs if j.get("url") not in applied_urls]

    # Split into new vs previously seen
    new_jobs = [j for j in all_jobs if j.get("url") not in seen_urls]
    old_jobs = [j for j in all_jobs if j.get("url") in seen_urls] if include_seen else []

    # Update seen list
    for job in all_jobs:
        if job.get("url"):
            seen_urls.add(job["url"])
    save_json(SEEN_FILE, list(seen_urls))

    # Send email for new jobs
    if new_jobs:
        candidate_name = resume.get("name", "Candidate")
        print(f"  Sending email for {len(new_jobs)} new job(s)...")
        try:
            send_email(new_jobs, candidate_name)
        except Exception as e:
            print(f"  ⚠️  Email failed: {e}")

    jobs_sorted = sorted(all_jobs if include_seen else new_jobs,
                         key=lambda x: x.get("relevance_score", 0), reverse=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "candidate": resume.get("name", ""),
        "total_jobs": len(jobs_sorted),
        "new_jobs": len(new_jobs),
        "jobs": jobs_sorted,
    }

    save_json(JOBS_FILE, output)
    return output
```

with:

```python
    def _verify_open(url: str) -> bool:
        greenhouse = job_freshness.parse_greenhouse(url)
        if greenhouse:
            return job_freshness.check_greenhouse_open(*greenhouse)
        lever = job_freshness.parse_lever(url)
        if lever:
            return job_freshness.check_lever_open(*lever)
        try:
            result = tavily_client.extract(urls=[url])
            content = result["results"][0].get("raw_content", "") if result.get("results") else ""
        except Exception:
            return True
        return not job_freshness.looks_closed(content)

    store = job_store.load_store(profile_slug)
    now = datetime.now()
    now_iso = now.isoformat()

    ids_before = set(store.get("jobs", {}).keys())
    job_store.process_search_results(all_jobs, store, now_iso, verify_open=_verify_open)
    job_store.reverify_stale_jobs(store, now, verify_open=_verify_open)

    newly_added_ids = set(store.get("jobs", {}).keys()) - ids_before
    freshly_new_jobs = [store["jobs"][jid] for jid in newly_added_ids]

    if freshly_new_jobs:
        candidate_name = resume.get("name", "Candidate")
        print(f"  Sending email for {len(freshly_new_jobs)} new job(s)...")
        try:
            send_email(freshly_new_jobs, candidate_name)
        except Exception as e:
            print(f"  ⚠️  Email failed: {e}")

    job_store.save_store(profile_slug, store)

    visible = job_store.visible_jobs(store)
    jobs_sorted = visible if include_seen else [j for j in visible if j.get("status") == "new"]

    output = {
        "generated_at": now_iso,
        "candidate": resume.get("name", ""),
        "total_jobs": len(jobs_sorted),
        "new_jobs": len([j for j in visible if j.get("status") == "new"]),
        "jobs": jobs_sorted,
    }
    return output
```

- [ ] **Step 5: Replace `mark_applied`**

Replace:

```python
def mark_applied(url: str) -> None:
    applied = set(load_json(APPLIED_FILE, []))
    applied.add(url)
    save_json(APPLIED_FILE, list(applied))
    print(f"✅ Marked as applied: {url}")
```

with:

```python
def mark_applied(url: str, profile_slug: str = "") -> bool:
    store = job_store.load_store(profile_slug)
    job_id = job_store.make_job_id(url)
    ok = job_store.mark_status(store, job_id, "applied")
    if ok:
        job_store.save_store(profile_slug, store)
        print(f"✅ Marked as applied: {url}")
    else:
        print(f"⚠️  URL not found in job store, nothing to mark: {url}")
    return ok
```

- [ ] **Step 6: Fix the one call site in `agents/main_agent.py`**

In `agents/main_agent.py`, replace:

```python
    if args.applied:
        job_search_agent.mark_applied(args.applied)
        return
```

with:

```python
    if args.applied:
        job_search_agent.mark_applied(args.applied, profile_slug)
        return
```

- [ ] **Step 7: Verify by inspection and a dry run against a fixture store**

Run:
```bash
JOBS_OUTPUT_DIR=/tmp/job-store-smoke python3 -c "
import sys
sys.path.insert(0, 'agents')
import job_search_agent, job_store

store = job_store.load_store('smoke-test')
job_store.merge_job(store, {
    'source': 'greenhouse', 'title': 'Data Engineer', 'company': 'Acme',
    'location': 'London', 'url': 'https://boards.greenhouse.io/acme/jobs/1',
    'relevance_score': 8, 'match_reason': 'fits',
}, '2026-07-17T00:00:00')
job_store.save_store('smoke-test', store)

ok = job_search_agent.mark_applied('https://boards.greenhouse.io/acme/jobs/1', 'smoke-test')
print('mark_applied returned:', ok)
reloaded = job_store.load_store('smoke-test')
print('status after mark:', list(reloaded['jobs'].values())[0]['status'])
"
```
Expected: `mark_applied returned: True` then `status after mark: applied`

- [ ] **Step 8: Commit**

```bash
git add agents/job_search_agent.py agents/main_agent.py
git commit -m "feat: wire job_search_agent.run() to the persistent store with freshness checks"
```

---

## Task 13: `a2a/routes/job_search.py` — REST endpoints

**Files:**
- Create: `a2a/routes/job_search.py`
- Test: `tests/test_job_search_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_job_search_api.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    monkeypatch.setenv("JOBS_OUTPUT_DIR", str(tmp_path / "output"))
    profile_dir = tmp_path / "profiles" / "test-user"
    profile_dir.mkdir(parents=True)
    (profile_dir / "resume_data.json").write_text(json.dumps({"name": "Test User"}))
    return tmp_path


@pytest.fixture
def client(dirs, monkeypatch):
    import importlib
    import a2a.routes.job_search as mod
    importlib.reload(mod)
    monkeypatch.setattr(mod.job_search_agent, "run", lambda resume, profile_slug="": {
        "generated_at": "2026-07-17T00:00:00", "jobs": [],
    })
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app), mod


def test_start_search_404_when_no_resume(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/unknown-user/job-search")
    assert resp.status_code == 404


def test_start_search_returns_searching_status(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/test-user/job-search")
    assert resp.status_code == 200
    assert resp.json() == {"status": "searching"}


def test_start_search_409_when_already_running(client):
    test_client, mod = client
    mod._running.add("test-user")
    resp = test_client.post("/api/profiles/test-user/job-search")
    assert resp.status_code == 409
    mod._running.discard("test-user")


def test_get_job_search_returns_searching_while_running(client):
    test_client, mod = client
    mod._running.add("test-user")
    resp = test_client.get("/api/profiles/test-user/job-search")
    assert resp.json() == {"status": "searching"}
    mod._running.discard("test-user")


def test_get_job_search_returns_jobs_when_idle(client, dirs):
    test_client, mod = client
    import job_store
    store = job_store.load_store("test-user")
    job_store.merge_job(store, {
        "source": "greenhouse", "title": "Data Engineer", "company": "Acme",
        "location": "London", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "relevance_score": 8, "match_reason": "fits",
    }, "2026-07-17T00:00:00")
    job_store.save_store("test-user", store)

    resp = test_client.get("/api/profiles/test-user/job-search")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["status"] == "new"

    resp2 = test_client.get("/api/profiles/test-user/job-search")
    assert resp2.json()["jobs"][0]["status"] == "seen"


def test_apply_to_job_marks_status(client, dirs):
    test_client, mod = client
    import job_store
    store = job_store.load_store("test-user")
    job_store.merge_job(store, {
        "source": "greenhouse", "title": "Data Engineer", "company": "Acme",
        "location": "London", "url": "https://boards.greenhouse.io/acme/jobs/1",
        "relevance_score": 8, "match_reason": "fits",
    }, "2026-07-17T00:00:00")
    job_store.save_store("test-user", store)
    job_id = list(store["jobs"].keys())[0]

    resp = test_client.post(f"/api/profiles/test-user/job-search/{job_id}/apply")
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"


def test_dismiss_job_404_for_unknown_id(client):
    test_client, mod = client
    resp = test_client.post("/api/profiles/test-user/job-search/unknown-id/dismiss")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_job_search_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'a2a.routes.job_search'`

- [ ] **Step 3: Write the implementation**

```python
# a2a/routes/job_search.py
import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import job_store
import job_search_agent

router = APIRouter(prefix="/api/profiles", tags=["job-search"])

_running: set = set()


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR",
                          str(Path(__file__).parent.parent.parent / "data" / "profiles"))
    return Path(base)


def _resume_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_data.json"


def _run_search(slug: str) -> None:
    try:
        resume = json.loads(_resume_file(slug).read_text(encoding="utf-8"))
        job_search_agent.run(resume, profile_slug=slug)
    finally:
        _running.discard(slug)


@router.post("/{slug}/job-search")
def start_job_search(slug: str, background_tasks: BackgroundTasks):
    if not _resume_file(slug).exists():
        raise HTTPException(status_code=404, detail="No resume data for this profile")
    if slug in _running:
        raise HTTPException(status_code=409, detail="A search is already running for this profile")
    _running.add(slug)
    background_tasks.add_task(_run_search, slug)
    return {"status": "searching"}


@router.get("/{slug}/job-search")
def get_job_search(slug: str):
    if slug in _running:
        return {"status": "searching"}
    store = job_store.load_store(slug)
    jobs = job_store.visible_jobs(store)
    if job_store.mark_new_as_seen(store):
        job_store.save_store(slug, store)
    return {"generated_at": store.get("generated_at", ""), "jobs": jobs}


@router.post("/{slug}/job-search/{job_id}/apply")
def apply_to_job(slug: str, job_id: str):
    store = job_store.load_store(slug)
    if not job_store.mark_status(store, job_id, "applied"):
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.save_store(slug, store)
    return {"id": job_id, "status": "applied"}


@router.post("/{slug}/job-search/{job_id}/dismiss")
def dismiss_job(slug: str, job_id: str):
    store = job_store.load_store(slug)
    if not job_store.mark_status(store, job_id, "dismissed"):
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.save_store(slug, store)
    return {"id": job_id, "status": "dismissed"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_job_search_api.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/job_search.py tests/test_job_search_api.py
git commit -m "feat: add job-search REST endpoints (trigger, poll, apply, dismiss)"
```

---

## Task 14: Register the router in `a2a/server.py`

**Files:**
- Modify: `a2a/server.py:41`, `:64`

- [ ] **Step 1: Add the import**

Replace:

```python
from .routes import profiles, applications, tailor_api, search_brief
```

with:

```python
from .routes import profiles, applications, tailor_api, search_brief, job_search as job_search_routes
```

- [ ] **Step 2: Register the router**

Replace:

```python
app.include_router(profiles.router)
app.include_router(applications.router)
app.include_router(tailor_api.router)
app.include_router(search_brief.router)
```

with:

```python
app.include_router(profiles.router)
app.include_router(applications.router)
app.include_router(tailor_api.router)
app.include_router(search_brief.router)
app.include_router(job_search_routes.router)
```

- [ ] **Step 3: Verify the app starts and lists the new routes**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from a2a.server import app
paths = sorted(r.path for r in app.routes if hasattr(r, 'path') and 'job-search' in r.path)
print(paths)
"
```
Expected: `['/api/profiles/{slug}/job-search', '/api/profiles/{slug}/job-search/{job_id}/apply', '/api/profiles/{slug}/job-search/{job_id}/dismiss']`

- [ ] **Step 4: Commit**

```bash
git add a2a/server.py
git commit -m "feat: register job-search router on the FastAPI app"
```

---

## Task 15: Delete the superseded legacy test script

**Files:**
- Delete: `tests/test_job_search.py`

- [ ] **Step 1: Confirm it's already broken (pre-existing, not caused by this plan)**

Run: `python3 -m pytest tests/test_job_search.py -v`
Expected: ERROR — `FileNotFoundError: [Errno 2] No such file or directory: 'data/resume_data.json'` (confirms it was already dead before this plan touched anything)

- [ ] **Step 2: Delete it**

```bash
git rm tests/test_job_search.py
```

- [ ] **Step 3: Run the full backend test suite excluding the other known-broken live script**

Run: `python3 -m pytest tests/ -v --ignore=tests/test_tailor.py --ignore=tests/test_linkedin.py`
Expected: PASS — all tests green (the two ignored files are pre-existing live scripts with the same "no test_ functions, hits real APIs" pattern, unrelated to this plan)

- [ ] **Step 4: Commit**

```bash
git commit -m "test: remove superseded job_search script (broken since data/resume_data.json moved)"
```

---

## Task 16: Frontend types — `JobMatch`

**Files:**
- Modify: `web/lib/types.ts`

- [ ] **Step 1: Append the new types**

Add to the end of `web/lib/types.ts`:

```typescript
export type JobSource = "linkedin" | "greenhouse" | "lever" | "yc";
export type JobStatus = "new" | "seen" | "applied" | "dismissed" | "closed";

export interface JobMatch {
  id: string;
  source: JobSource;
  title: string;
  company: string;
  location: string;
  url: string;
  relevance_score: number;
  match_reason: string;
  status: JobStatus;
  first_seen_at: string;
  last_seen_at: string;
}

export interface JobSearchResult {
  status?: "searching";
  generated_at?: string;
  jobs?: JobMatch[];
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/lib/types.ts
git commit -m "feat: add JobMatch and JobSearchResult types"
```

---

## Task 17: Frontend API client — job search functions

**Files:**
- Modify: `web/lib/api.ts`

- [ ] **Step 1: Add the import and the four client functions**

Change the top import line:

```typescript
import type { Application, ApplicationStatus, Profile, TailorJob, TailoredResume, SearchBrief, Signal } from "./types";
```

to:

```typescript
import type { Application, ApplicationStatus, Profile, TailorJob, TailoredResume, SearchBrief, Signal, JobMatch, JobSearchResult } from "./types";
```

Append to the end of the file:

```typescript
// Job Search
export const searchJobs = (slug: string) =>
  req<{ status: string }>(`/profiles/${slug}/job-search`, { method: "POST" });

export const getJobMatches = (slug: string) =>
  req<JobSearchResult>(`/profiles/${slug}/job-search`);

export const applyToJob = (slug: string, jobId: string) =>
  req<{ id: string; status: string }>(`/profiles/${slug}/job-search/${jobId}/apply`, { method: "POST" });

export const dismissJob = (slug: string, jobId: string) =>
  req<{ id: string; status: string }>(`/profiles/${slug}/job-search/${jobId}/dismiss`, { method: "POST" });
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/lib/api.ts
git commit -m "feat: add job-search API client functions"
```

---

## Task 18: `web/components/JobCard.tsx`

**Files:**
- Create: `web/components/JobCard.tsx`

- [ ] **Step 1: Write the component**

```typescript
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { JobMatch } from "@/lib/types";
import * as api from "@/lib/api";
import { ExternalLink, Wand2, Check, X } from "lucide-react";

const SOURCE_LABEL: Record<JobMatch["source"], string> = {
  linkedin: "LinkedIn",
  greenhouse: "Greenhouse",
  lever: "Lever",
  yc: "Y Combinator",
};

const SOURCE_COLOUR: Record<JobMatch["source"], string> = {
  linkedin: "bg-accent-light text-accent",
  greenhouse: "bg-green-soft text-green-text",
  lever: "bg-yellow-50 text-yellow-700",
  yc: "bg-cream text-navy border border-warm-border",
};

export function JobCard({
  job,
  profile,
  onRemove,
}: {
  job: JobMatch;
  profile: string;
  onRemove: (id: string) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleApply() {
    setBusy(true);
    try {
      await api.applyToJob(profile, job.id);
      onRemove(job.id);
    } finally {
      setBusy(false);
    }
  }

  async function handleDismiss() {
    setBusy(true);
    try {
      await api.dismissJob(profile, job.id);
      onRemove(job.id);
    } finally {
      setBusy(false);
    }
  }

  async function handleTailor() {
    setBusy(true);
    try {
      const res = await api.startTailor(profile, job.url);
      router.push(`/tailor?job=${res.job_id}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-warm-border rounded-2xl p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-navy">{job.title}</h3>
            {job.status === "new" && (
              <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-accent text-white">New</span>
            )}
          </div>
          <p className="text-sm text-muted">{job.company} · {job.location}</p>
        </div>
        <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full shrink-0 ${SOURCE_COLOUR[job.source]}`}>
          {SOURCE_LABEL[job.source]}
        </span>
      </div>

      <p className="text-sm text-navy">{job.match_reason}</p>
      <p className="text-xs text-muted">Match score: {job.relevance_score}/10</p>

      <div className="flex items-center gap-2 pt-1">
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm font-medium text-navy hover:text-accent transition-colors"
        >
          <ExternalLink size={14} /> View
        </a>
        <button
          onClick={handleTailor}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-navy hover:text-accent transition-colors disabled:opacity-50"
        >
          <Wand2 size={14} /> Tailor
        </button>
        <button
          onClick={handleApply}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-green-text hover:opacity-80 transition-opacity disabled:opacity-50 ml-auto"
        >
          <Check size={14} /> Applied
        </button>
        <button
          onClick={handleDismiss}
          disabled={busy}
          className="flex items-center gap-1.5 text-sm font-medium text-muted hover:text-red-600 transition-colors disabled:opacity-50"
        >
          <X size={14} /> Dismiss
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors (this component isn't imported anywhere yet, so this just checks it parses cleanly)

- [ ] **Step 3: Commit**

```bash
git add web/components/JobCard.tsx
git commit -m "feat: add JobCard component with source badge and apply/dismiss/tailor actions"
```

---

## Task 19: `web/app/jobs/page.tsx`

**Files:**
- Create: `web/app/jobs/page.tsx`

- [ ] **Step 1: Write the page**

```typescript
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import type { JobMatch } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { JobCard } from "@/components/JobCard";
import { Search, Loader2 } from "lucide-react";

export default function JobsPage() {
  const profile = useActiveProfile();
  const [jobs, setJobs] = useState<JobMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const result = await api.getJobMatches(profile);
      if (result.status === "searching") {
        setSearching(true);
      } else {
        setSearching(false);
        setJobs(result.jobs ?? []);
      }
    } catch {
      setError("Failed to load job matches.");
    } finally {
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!searching) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    pollRef.current = setInterval(load, 3000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [searching, load]);

  async function handleSearch() {
    if (!profile) return;
    setError("");
    try {
      await api.searchJobs(profile);
      setSearching(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start search");
    }
  }

  function handleRemove(id: string) {
    setJobs((prev) => prev.filter((j) => j.id !== id));
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Jobs</h1>
          <p className="text-sm text-muted mt-1">{jobs.length} match{jobs.length !== 1 ? "es" : ""}</p>
        </div>
        <button
          onClick={handleSearch}
          disabled={searching || !profile}
          className="flex items-center gap-1.5 bg-accent hover:bg-accent-hover text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
        >
          {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          {searching ? "Searching..." : "Search now"}
        </button>
      </div>

      {!profile && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
          Select a profile first.
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-4 text-sm text-red-600">
          {error}
        </div>
      )}

      {profile && !loading && !searching && jobs.length === 0 && (
        <div className="bg-cream border border-warm-border rounded-2xl px-5 py-8 text-center text-sm text-muted">
          No matches yet — click Search now.
        </div>
      )}

      <div className="space-y-3">
        {jobs.map((job) => (
          <JobCard key={job.id} job={job} profile={profile} onRemove={handleRemove} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/app/jobs/page.tsx
git commit -m "feat: add Jobs page with search-now trigger and polling"
```

---

## Task 20: Add "Jobs" to `TopNav.tsx`

**Files:**
- Modify: `web/components/TopNav.tsx`

- [ ] **Step 1: Add the icon import and nav entry**

Replace:

```typescript
import { LayoutDashboard, FileText, Briefcase, Search, Info } from "lucide-react";
```

with:

```typescript
import { LayoutDashboard, FileText, Briefcase, Search, ListChecks, Info } from "lucide-react";
```

Replace:

```typescript
const nav = [
  { href: "/",             label: "Dashboard",    icon: LayoutDashboard },
  { href: "/tailor",       label: "Tailor Resume", icon: FileText },
  { href: "/applications", label: "Applications",  icon: Briefcase },
  { href: "/search-brief", label: "Search Brief",  icon: Search },
  { href: "/about",        label: "About",          icon: Info },
];
```

with:

```typescript
const nav = [
  { href: "/",             label: "Dashboard",    icon: LayoutDashboard },
  { href: "/tailor",       label: "Tailor Resume", icon: FileText },
  { href: "/jobs",         label: "Jobs",          icon: ListChecks },
  { href: "/applications", label: "Applications",  icon: Briefcase },
  { href: "/search-brief", label: "Search Brief",  icon: Search },
  { href: "/about",        label: "About",          icon: Info },
];
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/components/TopNav.tsx
git commit -m "feat: add Jobs entry to top navigation"
```

---

## Task 21: Fix Tailor page's restore-polling gap

**Files:**
- Modify: `web/app/tailor/page.tsx`

**Why:** the Jobs page's "Tailor" button (Task 18) starts a tailor job and navigates to `/tailor?job=<id>` while it's still running. The existing restore effect only fetches status once and never resumes polling, so a job started this way would show one stale "running" snapshot forever instead of updating to completed.

- [ ] **Step 1: Update the restore effect**

Replace:

```typescript
  // Restore completed job when redirected back from the edit page
  useEffect(() => {
    const jobParam = searchParams.get("job");
    if (!jobParam || job) return;
    api.getTailorStatus(jobParam).then(setJob).catch(() => {});
  }, [searchParams, job]);
```

with:

```typescript
  // Restore a job when arriving via ?job= — either completed (redirect back from
  // the edit page) or still running (started from the Jobs page's Tailor button).
  useEffect(() => {
    const jobParam = searchParams.get("job");
    if (!jobParam || job) return;
    api.getTailorStatus(jobParam).then((status) => {
      setJob(status);
      if (status.status === "running") setPolling(true);
    }).catch(() => {});
  }, [searchParams, job]);
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add web/app/tailor/page.tsx
git commit -m "fix: resume polling when a running tailor job is restored via ?job="
```

---

## Task 22: End-to-end manual smoke test

**Files:** none (verification checkpoint)

- [ ] **Step 1: Start the backend**

Run: `python3 -m uvicorn a2a.server:app --port 8000` (background/separate terminal)
Expected: starts without import errors; confirms Task 14's router registration didn't break app startup

- [ ] **Step 2: Start the frontend**

Run: `cd web && npm run dev` (background/separate terminal)

- [ ] **Step 3: Walk the golden path in a browser**

1. Open `http://localhost:3000`, select the `rohit` profile.
2. Navigate to the new "Jobs" nav item — confirm the empty state ("No matches yet — click Search now") renders.
3. Click "Search now" — confirm the button shows a spinner and "Searching...", and polling starts (Network tab shows repeated `GET /api/profiles/rohit/job-search` every 3s).
4. Once results land, confirm: source badges show correct labels/colours, "New" badge appears on freshly found jobs, match reason and score render.
5. Click "View" on a job — confirms it opens the job URL in a new tab.
6. Click "Tailor" on a job — confirms it navigates to `/tailor?job=<id>` and the Tailor page shows "running" then transitions to a completed state without a manual refresh (this is the Task 21 fix in action).
7. Go back to Jobs, click "Applied" on one job and "Dismiss" on another — confirm both disappear from the list immediately.
8. Reload the Jobs page — confirm the applied/dismissed jobs stay gone (persisted, not just removed client-side) and previously "new" jobs now show without the "New" badge (transitioned to "seen").

- [ ] **Step 4: Confirm the CLI path still works**

Run: `python3 agents/main_agent.py --jobs-only --profile rohit`
Expected: runs without error, prints matched jobs, and `output/profiles/rohit/jobs.json` is created/updated (confirms Task 12's `main_agent.py` fix and the per-profile path fix from Task 1 both work together)

- [ ] **Step 5: Report findings**

No commit for this task — if any step reveals a bug, fix it as a new small commit and re-run the affected step before moving on.
