# Resume Versioning & AI Section Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user update their base resume over time — add a project, note a new skill, correct an entry — through a per-section AI-drafted editor instead of re-uploading a whole document, with every change (including the existing full-file replace) versioned in a capped history with restore support.

**Architecture:** A new plain-function module `a2a/resume_history.py` owns `resume_data.json` reads/writes and a capped (20-entry) `resume_history.json` snapshot log; both the existing full-file-replace endpoint and a new `a2a/routes/resume_versions.py` router call into it. The new router exposes history (list/get/restore) and section (`draft`/`apply`) endpoints across four section shapes — list-of-objects, flat list, grouped list (Skills), and scalar fields. The frontend gets a new `/profile/[slug]/edit` page with per-section Add/Edit/Delete controls (instruction → AI draft → editable preview → confirm/cancel) and a history panel; the existing Replace Resume modal moves there from the read-only profile page.

**Tech Stack:** Python 3.9, FastAPI, Anthropic SDK (existing `core/config.py` MODEL + JSON extraction helpers), pytest; Next.js 14 / TypeScript / Tailwind, existing `web/lib/api.ts` + `web/lib/types.ts` conventions.

## Global Constraints

- Python 3.9 syntax: `Optional[str]`, `List[dict]`, `Dict[str, str]` — never `str | None` / `list[dict]`.
- Never define `MODEL = "claude-..."` locally — import from `core/config.py`.
- Never write directly to `data/` from the frontend — always through API routes.
- No `allow_origins=["*"]` — not touched by this plan, existing CORS config is unaffected.
- Mock only the true external boundary (the Anthropic API call) in tests; everything else runs against real files via `tmp_path` + `PROFILES_DIR` env var, matching `tests/test_profiles_api.py` / `tests/test_search_brief_api.py`.
- No frontend test runner exists in this repo (`web/package.json` has no test script) — frontend tasks are verified with `npm run typecheck` plus manual verification in the running dev server, not fabricated unit tests.
- Every new page must work without being added to `web/components/TopNav.tsx` — `TopNav` only lists top-level sections (Dashboard, Tailor Resume, Jobs, Applications, Search Brief, About); nested routes like `/profile/[slug]` and `/profile/[slug]/edit` are reached via in-page links, not the top nav, matching the existing pattern.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| CREATE | `a2a/resume_history.py` | Plain functions: load/save current resume, push/prune/restore versioned history |
| CREATE | `tests/test_resume_history.py` | Tests for the above |
| MODIFY | `a2a/routes/profiles.py` | `confirm_resume` pushes a history snapshot before overwriting |
| CREATE | `a2a/routes/resume_versions.py` | History endpoints + section `draft`/`apply` endpoints |
| CREATE | `tests/test_resume_versions_api.py` | Tests for the above |
| MODIFY | `a2a/server.py` | Mount the new router |
| MODIFY | `web/lib/types.ts` | `ResumeVersionSummary`, `ResumeVersion`, `SectionDraftRequest/Response`, `SectionApplyRequest` |
| MODIFY | `web/lib/api.ts` | `getResumeHistory`, `getResumeVersion`, `restoreResumeVersion`, `draftResumeSection`, `applyResumeSection` |
| CREATE | `web/components/resume-edit/SectionInstructionBox.tsx` | Instruction textarea + submit/cancel, used by every Add/Edit flow |
| CREATE | `web/components/resume-edit/EditableItemForm.tsx` | Generic editable form for a drafted JSON object/string, used in every preview step |
| CREATE | `web/components/resume-edit/HistoryPanel.tsx` | Version list, view snapshot, restore |
| CREATE | `web/app/profile/[slug]/edit/page.tsx` | The edit page itself: section blocks, Add/Edit/Delete wiring, history panel, Replace Resume |
| MODIFY | `web/app/profile/[slug]/page.tsx` | Remove Replace Resume button/modal, add a link to `/edit` |

---

## Data Structures

### `data/profiles/{slug}/resume_history.json`

```json
{
  "versions": [
    {
      "id": "a1b2c3d4",
      "timestamp": "2026-07-24T10:00:00+00:00",
      "change_summary": "Added Experience: Senior Data Engineer",
      "data": { "...": "full resume_data.json snapshot as it was before this change" }
    }
  ]
}
```

Capped at 20 entries, oldest dropped first.

### Section kind table (shared by backend and frontend)

| Kind | Sections | Item shape |
|---|---|---|
| `list_object` | `experience`, `education`, `certifications` | JSON object, fields inferred from an existing entry |
| `flat_list` | `languages` | plain string |
| `grouped_list` | `skills` | `{"group": str, "skill": str}` |
| `scalar` | `name`, `designation`, `work_right`, `email`, `phone`, `website`, `summary` | plain string, edit-only |

---

### Task 1: `resume_history.py` — versioned storage core

**Files:**
- Create: `a2a/resume_history.py`
- Test: `tests/test_resume_history.py`

**Interfaces:**
- Produces: `load_current(slug: str) -> Optional[dict]`, `save_current(slug: str, data: dict) -> None`, `load_history(slug: str) -> List[dict]`, `save_history(slug: str, versions: List[dict]) -> None`, `push_version(slug: str, change_summary: str) -> None`, `get_version(slug: str, version_id: str) -> Optional[dict]`, `restore_version(slug: str, version_id: str) -> Optional[dict]`, constant `MAX_HISTORY_VERSIONS = 20`. All read `PROFILES_DIR` env var the same way as `a2a/routes/profiles.py::_profiles_dir`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resume_history.py
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import a2a.resume_history as rh


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    p = tmp_path / "profiles" / "test-user"
    p.mkdir(parents=True)
    return p


def test_load_current_missing_file_returns_none(profiles_dir):
    assert rh.load_current("test-user") is None


def test_save_and_load_current_round_trip(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    assert rh.load_current("test-user") == {"name": "Ada"}


def test_load_history_missing_file_returns_empty_list(profiles_dir):
    assert rh.load_history("test-user") == []


def test_push_version_noop_when_no_current_resume(profiles_dir):
    rh.push_version("test-user", "Some change")
    assert rh.load_history("test-user") == []


def test_push_version_snapshots_current_state(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    rh.push_version("test-user", "Added Experience: Engineer")
    versions = rh.load_history("test-user")
    assert len(versions) == 1
    assert versions[0]["change_summary"] == "Added Experience: Engineer"
    assert versions[0]["data"] == {"name": "Ada"}
    assert "id" in versions[0] and "timestamp" in versions[0]


def test_push_version_caps_at_max(profiles_dir):
    rh.save_current("test-user", {"n": 0})
    for i in range(1, rh.MAX_HISTORY_VERSIONS + 5):
        rh.save_current("test-user", {"n": i})
        rh.push_version("test-user", f"Change {i}")
    versions = rh.load_history("test-user")
    assert len(versions) == rh.MAX_HISTORY_VERSIONS
    assert versions[0]["change_summary"] == "Change 5"
    assert versions[-1]["change_summary"] == f"Change {rh.MAX_HISTORY_VERSIONS + 4}"


def test_get_version_found_and_not_found(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    rh.push_version("test-user", "Snapshot A")
    version_id = rh.load_history("test-user")[0]["id"]
    assert rh.get_version("test-user", version_id)["change_summary"] == "Snapshot A"
    assert rh.get_version("test-user", "nonexistent") is None


def test_restore_version_pushes_current_then_restores(profiles_dir):
    rh.save_current("test-user", {"name": "Version A"})
    rh.push_version("test-user", "Snapshot A")
    version_a_id = rh.load_history("test-user")[0]["id"]

    rh.save_current("test-user", {"name": "Version B"})

    restored = rh.restore_version("test-user", version_a_id)

    assert restored == {"name": "Version A"}
    assert rh.load_current("test-user") == {"name": "Version A"}
    versions = rh.load_history("test-user")
    assert len(versions) == 2
    assert versions[-1]["data"] == {"name": "Version B"}
    assert versions[-1]["change_summary"].startswith("Restored version from")


def test_restore_version_unknown_id_returns_none(profiles_dir):
    rh.save_current("test-user", {"name": "Ada"})
    assert rh.restore_version("test-user", "nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_resume_history.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'a2a.resume_history'`

- [ ] **Step 3: Write the implementation**

```python
# a2a/resume_history.py
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

MAX_HISTORY_VERSIONS = 20


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR", str(Path(__file__).parent.parent / "data" / "profiles"))
    return Path(base)


def _resume_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_data.json"


def _history_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_history.json"


def load_current(slug: str) -> Optional[dict]:
    f = _resume_file(slug)
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def save_current(slug: str, data: dict) -> None:
    f = _resume_file(slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_history(slug: str) -> List[dict]:
    f = _history_file(slug)
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("versions", [])


def save_history(slug: str, versions: List[dict]) -> None:
    f = _history_file(slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"versions": versions}, indent=2), encoding="utf-8")


def push_version(slug: str, change_summary: str) -> None:
    """Snapshot the CURRENT resume_data.json into history before it is overwritten.
    No-op if there is no current resume yet — nothing to snapshot."""
    current = load_current(slug)
    if current is None:
        return
    versions = load_history(slug)
    versions.append({
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "change_summary": change_summary,
        "data": current,
    })
    versions = versions[-MAX_HISTORY_VERSIONS:]
    save_history(slug, versions)


def get_version(slug: str, version_id: str) -> Optional[dict]:
    for v in load_history(slug):
        if v["id"] == version_id:
            return v
    return None


def restore_version(slug: str, version_id: str) -> Optional[dict]:
    """Push the current state to history, then make the given past version current.
    Returns the restored data, or None if version_id doesn't exist."""
    version = get_version(slug, version_id)
    if version is None:
        return None
    push_version(slug, f"Restored version from {version['timestamp']}")
    save_current(slug, version["data"])
    return version["data"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_resume_history.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add a2a/resume_history.py tests/test_resume_history.py
git commit -m "feat: add versioned resume history storage (push/prune/restore)"
```

---

### Task 2: Fold the existing full-file replace flow into history

**Files:**
- Modify: `a2a/routes/profiles.py:1-8` (imports), `a2a/routes/profiles.py` (`confirm_resume`, currently the last function in the file)
- Test: `tests/test_profiles_api.py`

**Interfaces:**
- Consumes: `a2a.resume_history.push_version(slug, change_summary)`, `a2a.resume_history.save_current(slug, data)` from Task 1.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_profiles_api.py

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
    assert resume == {"name": "New Resume"}

    history = json.loads((profiles_dir / slug / "resume_history.json").read_text())
    assert len(history["versions"]) == 1
    assert history["versions"][0]["change_summary"] == "Replaced via file upload"
    assert history["versions"][0]["data"] == {"name": "Old Resume"}
```

Add near the top of `tests/test_profiles_api.py`, alongside the existing imports:

```python
import json
```

(the file doesn't currently import `json` at module scope — check first; if `import json` already exists at the top, skip this addition).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_profiles_api.py::test_confirm_resume_pushes_history_before_overwriting -v`
Expected: FAIL — no `resume_history.json` is written (current `confirm_resume` overwrites directly with no snapshot)

- [ ] **Step 3: Modify `confirm_resume`**

In `a2a/routes/profiles.py`, add the import near the top (after the existing `from pydantic import BaseModel` line):

```python
from a2a import resume_history
```

Replace the existing `confirm_resume` function body:

```python
@router.post("/{slug}/resume/confirm")
def confirm_resume(slug: str):
    if slug not in _PARSE_CACHE:
        raise HTTPException(status_code=404, detail="No pending parse result for this profile. Run /parse first.")
    parsed = _PARSE_CACHE.pop(slug)
    resume_history.push_version(slug, "Replaced via file upload")
    resume_history.save_current(slug, parsed)
    return {"saved": True, "profile": slug}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_profiles_api.py -v`
Expected: PASS (all tests, including the new one)

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/profiles.py tests/test_profiles_api.py
git commit -m "fix: version the previous resume before a full-file replace"
```

---

### Task 3: History endpoints — list, get, restore

**Files:**
- Create: `a2a/routes/resume_versions.py`
- Create: `tests/test_resume_versions_api.py`

**Interfaces:**
- Consumes: everything from Task 1 (`a2a.resume_history`).
- Produces: `router` (FastAPI `APIRouter`, prefix `/api/profiles`) with `GET /{slug}/resume/history`, `GET /{slug}/resume/history/{version_id}`, `POST /{slug}/resume/history/{version_id}/restore`. Later tasks add more routes to this same `router` object.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resume_versions_api.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'a2a.routes.resume_versions'`

- [ ] **Step 3: Write the implementation**

```python
# a2a/routes/resume_versions.py
from fastapi import APIRouter, HTTPException

from a2a import resume_history

router = APIRouter(prefix="/api/profiles", tags=["resume-versions"])


@router.get("/{slug}/resume/history")
def list_history(slug: str):
    versions = resume_history.load_history(slug)
    return [
        {"id": v["id"], "timestamp": v["timestamp"], "change_summary": v["change_summary"]}
        for v in versions
    ]


@router.get("/{slug}/resume/history/{version_id}")
def get_history_version(slug: str, version_id: str):
    version = resume_history.get_version(slug, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{slug}/resume/history/{version_id}/restore")
def restore_history_version(slug: str, version_id: str):
    restored = resume_history.restore_version(slug, version_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"restored": True, "version_id": version_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/resume_versions.py tests/test_resume_versions_api.py
git commit -m "feat: add resume version history list/get/restore endpoints"
```

---

### Task 4: Section `apply` endpoint — all four section kinds

**Files:**
- Modify: `a2a/routes/resume_versions.py`
- Modify: `tests/test_resume_versions_api.py`

**Interfaces:**
- Consumes: `resume_history.load_current`, `resume_history.save_current`, `resume_history.push_version` (Task 1); the `router` object (Task 3).
- Produces: `POST /{slug}/resume/sections/{section}/apply`, request model `SectionApply`, module constants `LIST_OBJECT_SECTIONS`, `FLAT_LIST_SECTIONS`, `GROUPED_LIST_SECTIONS`, `SCALAR_SECTIONS`, `SECTION_LABELS`, `TITLE_FIELD`, function `_section_kind(section: str) -> str`. Task 5 (`draft`) reuses `_section_kind`, `SECTION_LABELS`, `TITLE_FIELD`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_resume_versions_api.py

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v`
Expected: FAIL — `apply` route does not exist yet (404 on all new tests)

- [ ] **Step 3: Write the implementation**

Add to `a2a/routes/resume_versions.py`:

```python
from typing import Any, Optional

from pydantic import BaseModel

LIST_OBJECT_SECTIONS = ("experience", "education", "certifications")
FLAT_LIST_SECTIONS = ("languages",)
GROUPED_LIST_SECTIONS = ("skills",)
SCALAR_SECTIONS = ("name", "designation", "work_right", "email", "phone", "website", "summary")

TITLE_FIELD = {"experience": "title", "education": "degree", "certifications": "name"}

SECTION_LABELS = {
    "experience": "Experience", "education": "Education", "certifications": "Certifications",
    "languages": "Languages", "skills": "Skills",
    "name": "Name", "designation": "Designation", "work_right": "Work Right", "email": "Email",
    "phone": "Phone", "website": "Website", "summary": "Summary",
}

FALLBACK_SCHEMA = {
    "experience": {"title": "", "highlight": "", "company": "", "location": "", "start_date": "", "end_date": "", "description": []},
    "education": {"degree": "", "school": "", "location": "", "start_date": "", "end_date": "", "gpa": ""},
    "certifications": {"name": "", "issuer": ""},
}


def _section_kind(section: str) -> str:
    if section in LIST_OBJECT_SECTIONS:
        return "list_object"
    if section in FLAT_LIST_SECTIONS:
        return "flat_list"
    if section in GROUPED_LIST_SECTIONS:
        return "grouped_list"
    if section in SCALAR_SECTIONS:
        return "scalar"
    raise HTTPException(status_code=400, detail=f"Unknown section: {section}")


class SectionApply(BaseModel):
    action: str
    item_index: Optional[int] = None
    group: Optional[str] = None
    skill: Optional[str] = None
    item: Optional[Any] = None


def _apply_list_object(resume: dict, section: str, body: SectionApply) -> str:
    items = resume.setdefault(section, [])
    title_field = TITLE_FIELD[section]
    label = SECTION_LABELS[section]

    if body.action == "add":
        new_items = body.item if isinstance(body.item, list) else [body.item]
        if not new_items:
            raise HTTPException(status_code=400, detail="No items to add")
        items.extend(new_items)
        names = ", ".join(str(i.get(title_field, "")) for i in new_items)
        return f"Added {label}: {names}"

    if body.item_index is None or not (0 <= body.item_index < len(items)):
        raise HTTPException(status_code=400, detail="item_index out of range")

    if body.action == "edit":
        if not isinstance(body.item, dict):
            raise HTTPException(status_code=400, detail="item must be an object")
        items[body.item_index] = body.item
        return f"Edited {label}: {body.item.get(title_field, '')}"

    if body.action == "delete":
        removed = items.pop(body.item_index)
        return f"Deleted {label}: {removed.get(title_field, '')}"

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _apply_flat_list(resume: dict, section: str, body: SectionApply) -> str:
    items = resume.setdefault(section, [])
    label = SECTION_LABELS[section]

    if body.action == "add":
        new_items = body.item if isinstance(body.item, list) else [body.item]
        if not new_items:
            raise HTTPException(status_code=400, detail="No items to add")
        items.extend(str(i) for i in new_items)
        return f"Added {label}: {', '.join(str(i) for i in new_items)}"

    if body.item_index is None or not (0 <= body.item_index < len(items)):
        raise HTTPException(status_code=400, detail="item_index out of range")

    if body.action == "edit":
        items[body.item_index] = str(body.item)
        return f"Edited {label}: {body.item}"

    if body.action == "delete":
        removed = items.pop(body.item_index)
        return f"Deleted {label}: {removed}"

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _apply_grouped_list(resume: dict, section: str, body: SectionApply) -> str:
    skills = resume.setdefault("skills", {})

    if body.action == "add":
        new_items = body.item if isinstance(body.item, list) else [body.item]
        if not new_items:
            raise HTTPException(status_code=400, detail="No items to add")
        groups_touched = []
        for entry in new_items:
            group, skill = entry["group"], entry["skill"]
            skills.setdefault(group, []).append(skill)
            if group not in groups_touched:
                groups_touched.append(group)
        return f"Added Skills: {', '.join(groups_touched)}"

    if body.group is None or body.skill is None:
        raise HTTPException(status_code=400, detail="group and skill are required")
    if body.group not in skills or body.skill not in skills[body.group]:
        raise HTTPException(status_code=400, detail="skill not found in group")

    if body.action == "edit":
        if not isinstance(body.item, dict):
            raise HTTPException(status_code=400, detail="item must be an object")
        new_group, new_skill = body.item["group"], body.item["skill"]
        skills[body.group].remove(body.skill)
        if not skills[body.group]:
            del skills[body.group]
        skills.setdefault(new_group, []).append(new_skill)
        return f"Edited Skills: {body.group}"

    if body.action == "delete":
        skills[body.group].remove(body.skill)
        if not skills[body.group]:
            del skills[body.group]
        return f"Deleted Skills: {body.group}"

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _apply_scalar(resume: dict, section: str, body: SectionApply) -> str:
    if body.action != "edit":
        raise HTTPException(status_code=400, detail=f"{section} only supports the edit action")
    resume[section] = body.item
    return f"Edited {SECTION_LABELS[section]}"


APPLY_HANDLERS = {
    "list_object": _apply_list_object,
    "flat_list": _apply_flat_list,
    "grouped_list": _apply_grouped_list,
    "scalar": _apply_scalar,
}


@router.post("/{slug}/resume/sections/{section}/apply")
def apply_section(slug: str, section: str, body: SectionApply):
    kind = _section_kind(section)
    resume = resume_history.load_current(slug)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    change_summary = APPLY_HANDLERS[kind](resume, section, body)

    resume_history.push_version(slug, change_summary)
    resume_history.save_current(slug, resume)
    return {"saved": True, "change_summary": change_summary}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v`
Expected: PASS (17 tests)

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/resume_versions.py tests/test_resume_versions_api.py
git commit -m "feat: add resume section apply endpoint (add/edit/delete, all section kinds)"
```

---

### Task 5: Section `draft` endpoint — AI-assisted drafting

**Files:**
- Modify: `a2a/routes/resume_versions.py`
- Modify: `tests/test_resume_versions_api.py`

**Interfaces:**
- Consumes: `_section_kind`, `SECTION_LABELS`, `FALLBACK_SCHEMA`, `LIST_OBJECT_SECTIONS`/`FLAT_LIST_SECTIONS`/`GROUPED_LIST_SECTIONS`/`SCALAR_SECTIONS` (Task 4); `MODEL`, `extract_json_object` from `core/config.py` (existing).
- Produces: `POST /{slug}/resume/sections/{section}/draft`, request model `SectionDraft`. Frontend Task 9-11 call this endpoint.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_resume_versions_api.py

class _FakeContent:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeContent(text)]


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def create(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeAnthropicClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def _mock_anthropic(monkeypatch, response_text):
    monkeypatch.setattr("anthropic.Anthropic", lambda: _FakeAnthropicClient(response_text))


def test_draft_add_list_object_section(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"items": [{"title": "New Role", "company": "NewCo", "description": ["Did stuff"]}]}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/experience/draft",
        json={"action": "add", "instruction": "I joined NewCo as a new role, did stuff"},
    )
    assert resp.status_code == 200
    assert resp.json()["items"][0]["title"] == "New Role"


def test_draft_edit_list_object_section(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"item": {"title": "Senior Data Engineer", "company": "Acme", "description": ["Built things"]}}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/experience/draft",
        json={"action": "edit", "item_index": 0, "instruction": "Add Senior to the title"},
    )
    assert resp.status_code == 200
    assert resp.json()["item"]["title"] == "Senior Data Engineer"


def test_draft_edit_out_of_range_index_400(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"item": {}}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/experience/draft",
        json={"action": "edit", "item_index": 9, "instruction": "X"},
    )
    assert resp.status_code == 400


def test_draft_add_flat_list_section(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"items": ["French", "German"]}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/languages/draft",
        json={"action": "add", "instruction": "I learned French and German"},
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == ["French", "German"]


def test_draft_add_grouped_list_section(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"items": [{"group": "Programming", "skill": "Python"}]}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/draft",
        json={"action": "add", "instruction": "I learned Python"},
    )
    assert resp.status_code == 200
    assert resp.json()["items"] == [{"group": "Programming", "skill": "Python"}]


def test_draft_edit_grouped_list_section(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"item": {"group": "Cloud", "skill": "Azure"}}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/skills/draft",
        json={"action": "edit", "group": "Cloud", "skill": "GCP", "instruction": "Replace with Azure"},
    )
    assert resp.status_code == 200
    assert resp.json()["item"] == {"group": "Cloud", "skill": "Azure"}


def test_draft_edit_scalar_section(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"item": "A punchier summary."}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/summary/draft",
        json={"action": "edit", "instruction": "Make it punchier"},
    )
    assert resp.status_code == 200
    assert resp.json()["item"] == "A punchier summary."


def test_draft_scalar_rejects_add_action(client, monkeypatch):
    _mock_anthropic(monkeypatch, '{"item": "X"}')
    resp = client.post(
        "/api/profiles/test-user/resume/sections/summary/draft",
        json={"action": "add", "instruction": "X"},
    )
    assert resp.status_code == 400


def test_draft_malformed_ai_response_returns_500(client, monkeypatch):
    _mock_anthropic(monkeypatch, "not valid json at all")
    resp = client.post(
        "/api/profiles/test-user/resume/sections/summary/draft",
        json={"action": "edit", "instruction": "Make it punchier"},
    )
    assert resp.status_code == 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v`
Expected: FAIL — `draft` route does not exist yet (404 on all new tests)

- [ ] **Step 3: Write the implementation**

Add to `a2a/routes/resume_versions.py`:

```python
import json as _json
import sys
from pathlib import Path

from pydantic import BaseModel as _BaseModel


class SectionDraft(_BaseModel):
    action: str
    item_index: Optional[int] = None
    group: Optional[str] = None
    skill: Optional[str] = None
    instruction: str


def _draft_prompt_list_object(resume: dict, section: str, body: SectionDraft) -> str:
    items = resume.get(section, [])
    if body.action == "edit":
        if body.item_index is None or not (0 <= body.item_index < len(items)):
            raise HTTPException(status_code=400, detail="item_index out of range")
        current = items[body.item_index]
        return f"""You are editing one entry in the "{section}" section of a resume.

Current entry:
{_json.dumps(current, indent=2)}

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": <the revised entry, same fields as the current entry>}}. Keep every field the current entry has; change only what the request asks for. Do not invent information not present in the current entry or the request."""

    if body.action == "add":
        example = items[0] if items else FALLBACK_SCHEMA[section]
        return f"""You are adding one or more new entries to the "{section}" section of a resume.

Existing entries follow this shape (example):
{_json.dumps(example, indent=2)}

Requested addition: {body.instruction}

Return ONLY a JSON object of the form {{"items": [<new entry>, ...]}} - one object per new entry described in the request, each matching the example's fields exactly. Use only information present in the request. Do not invent details."""

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _draft_prompt_flat_list(resume: dict, section: str, body: SectionDraft) -> str:
    items = resume.get(section, [])
    if body.action == "edit":
        if body.item_index is None or not (0 <= body.item_index < len(items)):
            raise HTTPException(status_code=400, detail="item_index out of range")
        current = items[body.item_index]
        return f"""You are editing one entry in the "{section}" section of a resume (a plain list of short text values).

Current value: "{current}"

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": "<revised value>"}}."""

    if body.action == "add":
        return f"""You are adding one or more new entries to the "{section}" section of a resume (a plain list of short text values).

Requested addition: {body.instruction}

Return ONLY a JSON object of the form {{"items": ["<value>", ...]}} - one string per new entry described in the request."""

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _draft_prompt_grouped_list(resume: dict, section: str, body: SectionDraft) -> str:
    skills = resume.get("skills", {})
    existing_groups = list(skills.keys())

    if body.action == "edit":
        if body.group is None or body.skill is None:
            raise HTTPException(status_code=400, detail="group and skill are required")
        return f"""You are editing one skill in a resume's Skills section.

Current skill: "{body.skill}" in group "{body.group}"

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": {{"group": "<group name>", "skill": "<skill name>"}}}}."""

    if body.action == "add":
        return f"""You are adding one or more new skills to a resume's Skills section.

Existing groups: {_json.dumps(existing_groups)}

Requested addition: {body.instruction}

Return ONLY a JSON object of the form {{"items": [{{"group": "<group name>", "skill": "<skill name>"}}, ...]}} - one entry per new skill described in the request. Reuse an existing group name where it fits; otherwise use a new, concise group name."""

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _draft_prompt_scalar(resume: dict, section: str, body: SectionDraft) -> str:
    if body.action != "edit":
        raise HTTPException(status_code=400, detail=f"{section} only supports the edit action")
    current = resume.get(section, "")
    return f"""You are editing the "{section}" field of a resume.

Current value: "{current}"

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": "<revised value>"}}."""


DRAFT_PROMPT_BUILDERS = {
    "list_object": _draft_prompt_list_object,
    "flat_list": _draft_prompt_flat_list,
    "grouped_list": _draft_prompt_grouped_list,
    "scalar": _draft_prompt_scalar,
}


@router.post("/{slug}/resume/sections/{section}/draft")
def draft_section(slug: str, section: str, body: SectionDraft):
    import anthropic
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
    from config import MODEL, extract_json_object

    kind = _section_kind(section)
    resume = resume_history.load_current(slug)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    prompt = DRAFT_PROMPT_BUILDERS[kind](resume, section, body)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return _json.loads(extract_json_object(response.content[0].text))
    except _json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Could not parse the AI's draft. Try rephrasing the instruction.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v`
Expected: PASS (26 tests)

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/resume_versions.py tests/test_resume_versions_api.py
git commit -m "feat: add AI-assisted resume section draft endpoint"
```

---

### Task 6: Mount the router

**Files:**
- Modify: `a2a/server.py:43`, `a2a/server.py:61-65`

**Interfaces:**
- Consumes: `a2a.routes.resume_versions.router` (Task 5).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_resume_versions_api.py, testing through the real app this time

def test_resume_versions_router_mounted_on_main_app():
    from a2a.server import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.get("/api/profiles/nonexistent-profile/resume/history")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_resume_versions_api.py::test_resume_versions_router_mounted_on_main_app -v`
Expected: FAIL — 404 Not Found (router isn't mounted on the app yet)

- [ ] **Step 3: Mount the router**

In `a2a/server.py`, change the import line:

```python
from .routes import profiles, applications, tailor_api, search_brief, job_search as job_search_routes, resume_versions
```

And add the router registration alongside the others:

```python
app.include_router(profiles.router)
app.include_router(applications.router)
app.include_router(tailor_api.router)
app.include_router(search_brief.router)
app.include_router(job_search_routes.router)
app.include_router(resume_versions.router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_resume_versions_api.py -v && python3 -m pytest tests/ -v`
Expected: PASS (full suite, no regressions)

- [ ] **Step 5: Commit**

```bash
git add a2a/server.py tests/test_resume_versions_api.py
git commit -m "feat: mount resume_versions router on the main app"
```

---

### Task 7: Frontend types + API client functions

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`

**Interfaces:**
- Produces: types `ResumeVersionSummary`, `ResumeVersion`, `SectionKind`, `SectionDraftRequest`, `SectionDraftResponse`, `SectionApplyRequest`; functions `getResumeHistory`, `getResumeVersion`, `restoreResumeVersion`, `draftResumeSection`, `applyResumeSection`. Used by Tasks 8-12.

- [ ] **Step 1: Add types**

Append to `web/lib/types.ts`:

```typescript
export interface ResumeVersionSummary {
  id: string;
  timestamp: string;
  change_summary: string;
}

export interface ResumeVersion extends ResumeVersionSummary {
  data: Record<string, unknown>;
}

export type SectionKind = "list_object" | "flat_list" | "grouped_list" | "scalar";

export interface SectionDraftRequest {
  action: "add" | "edit";
  item_index?: number;
  group?: string;
  skill?: string;
  instruction: string;
}

export interface SectionDraftResponse {
  items?: unknown[];
  item?: unknown;
}

export interface SectionApplyRequest {
  action: "add" | "edit" | "delete";
  item_index?: number;
  group?: string;
  skill?: string;
  item?: unknown;
}
```

- [ ] **Step 2: Add API client functions**

Update the import line at the top of `web/lib/api.ts`:

```typescript
import type { Application, ApplicationStatus, Profile, TailorJob, TailoredResume, SearchBrief, Signal, JobMatch, JobSearchResult, ResumeVersionSummary, ResumeVersion, SectionDraftRequest, SectionDraftResponse, SectionApplyRequest } from "./types";
```

Append near the existing resume-related functions (after `getResume`):

```typescript
export const getResumeHistory = (slug: string) =>
  req<ResumeVersionSummary[]>(`/profiles/${slug}/resume/history`);

export const getResumeVersion = (slug: string, versionId: string) =>
  req<ResumeVersion>(`/profiles/${slug}/resume/history/${versionId}`);

export const restoreResumeVersion = (slug: string, versionId: string) =>
  req<{ restored: boolean; version_id: string }>(`/profiles/${slug}/resume/history/${versionId}/restore`, {
    method: "POST",
  });

export const draftResumeSection = (slug: string, section: string, body: SectionDraftRequest) =>
  req<SectionDraftResponse>(`/profiles/${slug}/resume/sections/${section}/draft`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const applyResumeSection = (slug: string, section: string, body: SectionApplyRequest) =>
  req<{ saved: boolean; change_summary: string }>(`/profiles/${slug}/resume/sections/${section}/apply`, {
    method: "POST",
    body: JSON.stringify(body),
  });
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts
git commit -m "feat: add resume versioning types and API client functions"
```

---

### Task 8: Shared editing components — instruction box and editable form

**Files:**
- Create: `web/components/resume-edit/SectionInstructionBox.tsx`
- Create: `web/components/resume-edit/EditableItemForm.tsx`

**Interfaces:**
- Produces: `<SectionInstructionBox onSubmit={(instruction: string) => Promise<void>} onCancel={() => void} submitLabel={string} />`; `<EditableItemForm value={Record<string, unknown> | string} onChange={(next: Record<string, unknown> | string) => void} />`. Used by Tasks 9-11.

- [ ] **Step 1: Write `SectionInstructionBox.tsx`**

```typescript
// web/components/resume-edit/SectionInstructionBox.tsx
"use client";
import { useState } from "react";

interface Props {
  placeholder: string;
  submitLabel: string;
  onSubmit: (instruction: string) => Promise<void>;
  onCancel: () => void;
}

export function SectionInstructionBox({ placeholder, submitLabel, onSubmit, onCancel }: Props) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!instruction.trim()) return;
    setLoading(true);
    setError("");
    try {
      await onSubmit(instruction);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-surface rounded-lg p-3 space-y-2">
      <textarea
        value={instruction}
        onChange={e => setInstruction(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="w-full text-sm border border-gray-200 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-accent"
      />
      {error && <p className="text-xs text-red-500">{error}</p>}
      <div className="flex gap-2">
        <button
          onClick={onCancel}
          className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={loading || !instruction.trim()}
          className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 disabled:opacity-50 hover:bg-accent/90"
        >
          {loading ? "Drafting..." : submitLabel}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `EditableItemForm.tsx`**

```typescript
// web/components/resume-edit/EditableItemForm.tsx
"use client";

interface Props {
  value: Record<string, unknown> | string;
  onChange: (next: Record<string, unknown> | string) => void;
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every(x => typeof x === "string");
}

export function EditableItemForm({ value, onChange }: Props) {
  if (typeof value === "string") {
    return (
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={4}
        className="w-full text-sm border border-gray-200 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-accent"
      />
    );
  }

  return (
    <div className="space-y-2">
      {Object.entries(value).map(([key, fieldValue]) => (
        <div key={key}>
          <label className="block text-xs font-medium text-gray-500 mb-0.5">{key}</label>
          {isStringArray(fieldValue) ? (
            <textarea
              value={fieldValue.join("\n")}
              onChange={e => onChange({ ...value, [key]: e.target.value.split("\n") })}
              rows={Math.max(2, fieldValue.length)}
              className="w-full text-sm border border-gray-200 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          ) : (
            <input
              value={String(fieldValue ?? "")}
              onChange={e => onChange({ ...value, [key]: e.target.value })}
              className="w-full text-sm border border-gray-200 rounded-lg p-2 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add web/components/resume-edit/SectionInstructionBox.tsx web/components/resume-edit/EditableItemForm.tsx
git commit -m "feat: add shared instruction box and editable item form components"
```

---

### Task 9: Edit page skeleton — read-only sections, Replace Resume moved here

**Files:**
- Create: `web/app/profile/[slug]/edit/page.tsx`
- Modify: `web/app/profile/[slug]/page.tsx`

**Interfaces:**
- Consumes: `api.getResume`, `ReplaceResumeModal` (existing); Task 7's API functions (used by later tasks, not this one).
- Produces: the `EditPage` component and its `resume`/`setResume`/`loadResume` state, which Tasks 10-12 extend in place.

- [ ] **Step 1: Remove Replace Resume from the read-only profile page, add a link to `/edit`**

In `web/app/profile/[slug]/page.tsx`, remove the `Upload` import and `ReplaceResumeModal` import/usage, and the `showReplace` state, replacing the Replace Resume button with a link:

```typescript
"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { Code2, LayoutList, Copy, Check, Pencil } from "lucide-react";
```

Remove the `showReplace` state line and the `ReplaceResumeModal` block at the bottom of the file. Replace the Replace Resume button:

```typescript
          <Link
            href={`/profile/${slug}/edit`}
            className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
          >
            <Pencil size={13} />
            Edit
          </Link>
```

- [ ] **Step 2: Write the edit page skeleton**

```typescript
// web/app/profile/[slug]/edit/page.tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import * as api from "@/lib/api";
import { ArrowLeft, Upload } from "lucide-react";
import { ReplaceResumeModal } from "@/components/ReplaceResumeModal";

interface ResumeData {
  name?: string;
  designation?: string;
  work_right?: string;
  email?: string;
  phone?: string;
  website?: string;
  summary?: string;
  experience?: Record<string, unknown>[];
  skills?: Record<string, string[]>;
  education?: Record<string, unknown>[];
  certifications?: Record<string, unknown>[];
  languages?: string[];
  [key: string]: unknown;
}

export default function ResumeEditPage() {
  const { slug } = useParams<{ slug: string }>();
  const [resume, setResume] = useState<ResumeData | null>(null);
  const [error, setError] = useState("");
  const [showReplace, setShowReplace] = useState(false);

  const loadResume = useCallback(() => {
    if (!slug) return;
    api.getResume(slug)
      .then(data => {
        setResume(data as ResumeData);
        setError("");
      })
      .catch(() => setError("No resume data found for this profile."));
  }, [slug]);

  useEffect(() => { loadResume(); }, [loadResume]);

  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (!resume) return <p className="text-sm text-gray-400">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href={`/profile/${slug}`} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800">
          <ArrowLeft size={14} />
          Back to {resume.name ?? slug}
        </Link>
        <button
          onClick={() => setShowReplace(true)}
          className="flex items-center gap-1.5 text-xs text-gray-500 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
        >
          <Upload size={13} />
          Replace Resume
        </button>
      </div>

      <h1 className="text-xl font-bold text-gray-900">Edit Resume</h1>

      {/* Section editors are added in later tasks */}
      <p className="text-sm text-gray-400">Sections: Experience, Education, Certifications, Languages, Skills, and contact fields will render here.</p>

      {showReplace && slug && (
        <ReplaceResumeModal
          slug={slug}
          onClose={() => setShowReplace(false)}
          onReplaced={loadResume}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Manual verification**

Run: `cd web && npm run typecheck` (expect no errors), then `npm run dev` and open `/profile/rohit` in a browser — confirm the Replace Resume button is gone and an "Edit" link appears, and that it navigates to `/profile/rohit/edit`, showing the skeleton page with a working "Replace Resume" button (unchanged behaviour from before).

- [ ] **Step 4: Commit**

```bash
git add web/app/profile/[slug]/page.tsx web/app/profile/[slug]/edit/page.tsx
git commit -m "feat: add resume edit page skeleton, move Replace Resume there"
```

---

### Task 10: List-object section editing (Experience, Education, Certifications)

**Files:**
- Modify: `web/app/profile/[slug]/edit/page.tsx`

**Interfaces:**
- Consumes: `SectionInstructionBox`, `EditableItemForm` (Task 8); `api.draftResumeSection`, `api.applyResumeSection` (Task 7); `resume`/`setResume`/`loadResume` (Task 9).

- [ ] **Step 1: Add list-object section rendering and edit state**

Replace the placeholder paragraph in `web/app/profile/[slug]/edit/page.tsx` with real section rendering. Add these imports:

```typescript
import { Pencil, Trash2, Plus } from "lucide-react";
import { SectionInstructionBox } from "@/components/resume-edit/SectionInstructionBox";
import { EditableItemForm } from "@/components/resume-edit/EditableItemForm";
```

Add this state and helper inside `ResumeEditPage`, alongside the existing `resume`/`error`/`showReplace` state:

```typescript
  const [editing, setEditing] = useState<{ section: string; action: "add" | "edit"; itemIndex?: number; group?: string; skill?: string } | null>(null);
  const [drafted, setDrafted] = useState<unknown[] | unknown | null>(null);

  const TITLE_FIELD: Record<string, string> = { experience: "title", education: "degree", certifications: "name" };
  const SECTION_TITLES: Record<string, string> = { experience: "Experience", education: "Education", certifications: "Certifications" };

  async function handleDraft(section: string, instruction: string) {
    const target = editing;
    if (!target || !slug) return;
    const res = await api.draftResumeSection(slug, section, {
      action: target.action,
      item_index: target.itemIndex,
      group: target.group,
      skill: target.skill,
      instruction,
    });
    setDrafted(target.action === "add" ? res.items ?? [] : res.item ?? null);
  }

  async function handleConfirm(section: string) {
    if (!editing || !slug || drafted == null) return;
    await api.applyResumeSection(slug, section, {
      action: editing.action,
      item_index: editing.itemIndex,
      group: editing.group,
      skill: editing.skill,
      item: drafted,
    });
    setEditing(null);
    setDrafted(null);
    loadResume();
  }

  async function handleDelete(section: string, itemIndex: number) {
    if (!slug) return;
    if (!confirm("Delete this entry?")) return;
    await api.applyResumeSection(slug, section, { action: "delete", item_index: itemIndex });
    loadResume();
  }

  function renderListObjectSection(section: "experience" | "education" | "certifications") {
    const items = (resume?.[section] as Record<string, unknown>[] | undefined) ?? [];
    const titleField = TITLE_FIELD[section];
    return (
      <section key={section}>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">{SECTION_TITLES[section]}</h2>
        <div className="space-y-3">
          {items.map((item, i) => (
            <div key={i} className="bg-surface rounded-lg p-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-gray-800">{String(item[titleField] ?? "")}</p>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => { setEditing({ section, action: "edit", itemIndex: i }); setDrafted(null); }} className="text-gray-400 hover:text-gray-700">
                    <Pencil size={14} />
                  </button>
                  <button onClick={() => handleDelete(section, i)} className="text-gray-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {editing?.section === section && editing.action === "edit" && editing.itemIndex === i && (
                drafted == null ? (
                  <div className="mt-2">
                    <SectionInstructionBox
                      placeholder="Describe the change..."
                      submitLabel="Draft"
                      onSubmit={instruction => handleDraft(section, instruction)}
                      onCancel={() => setEditing(null)}
                    />
                  </div>
                ) : (
                  <div className="mt-2 space-y-2">
                    <EditableItemForm value={drafted as Record<string, unknown>} onChange={setDrafted} />
                    <div className="flex gap-2">
                      <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                      <button onClick={() => handleConfirm(section)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
                    </div>
                  </div>
                )
              )}
            </div>
          ))}
        </div>

        {editing?.section === section && editing.action === "add" ? (
          drafted == null ? (
            <div className="mt-3">
              <SectionInstructionBox
                placeholder={`Describe the new ${SECTION_TITLES[section].toLowerCase()} entry...`}
                submitLabel="Draft"
                onSubmit={instruction => handleDraft(section, instruction)}
                onCancel={() => setEditing(null)}
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              {(drafted as Record<string, unknown>[]).map((draftItem, i) => (
                <div key={i} className="bg-surface rounded-lg p-3">
                  <EditableItemForm
                    value={draftItem}
                    onChange={next => setDrafted((drafted as Record<string, unknown>[]).map((d, j) => (j === i ? next : d)))}
                  />
                </div>
              ))}
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleConfirm(section)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        ) : (
          <button
            onClick={() => { setEditing({ section, action: "add" }); setDrafted(null); }}
            className="mt-3 flex items-center gap-1 text-xs text-accent hover:underline"
          >
            <Plus size={13} /> Add new
          </button>
        )}
      </section>
    );
  }
```

Replace the placeholder paragraph with:

```typescript
      {renderListObjectSection("experience")}
      {renderListObjectSection("education")}
      {renderListObjectSection("certifications")}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 3: Manual verification**

Run: `python3 -m uvicorn a2a.server:app --port 8000` and `cd web && npm run dev`, open `/profile/rohit/edit`. Click "Add new" under Experience, type an instruction (e.g. "I joined Acme as a Consultant in 2026, led a data migration project"), confirm a draft appears with editable fields, edit a field, click Confirm, and verify the new entry appears in the list and persists on reload. Then test Edit and Delete on an existing entry.

- [ ] **Step 4: Commit**

```bash
git add web/app/profile/[slug]/edit/page.tsx
git commit -m "feat: add Experience/Education/Certifications editing to the resume edit page"
```

---

### Task 11: Skills, Languages, and scalar field editing

**Files:**
- Modify: `web/app/profile/[slug]/edit/page.tsx`

**Interfaces:**
- Consumes: same as Task 10.

- [ ] **Step 1: Add Skills section rendering**

Add inside `ResumeEditPage`, after `renderListObjectSection`:

```typescript
  function renderSkillsSection() {
    const skills = resume?.skills ?? {};
    return (
      <section key="skills">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Skills</h2>
        <div className="space-y-2">
          {Object.entries(skills).map(([group, list]) => (
            <div key={group} className="bg-surface rounded-lg p-3">
              <p className="text-xs font-medium text-gray-500 mb-1">{group}</p>
              <div className="flex flex-wrap gap-1.5">
                {list.map(skill => (
                  <span key={skill} className="flex items-center gap-1 bg-white border border-gray-200 rounded-full px-2 py-0.5 text-xs text-gray-700">
                    {skill}
                    <button onClick={() => { setEditing({ section: "skills", action: "edit", group, skill }); setDrafted(null); }} className="text-gray-400 hover:text-gray-700">
                      <Pencil size={11} />
                    </button>
                    <button onClick={() => handleDeleteSkill(group, skill)} className="text-gray-400 hover:text-red-500">
                      <Trash2 size={11} />
                    </button>
                  </span>
                ))}
              </div>
              {editing?.section === "skills" && editing.action === "edit" && editing.group === group && editing.skill && list.includes(editing.skill) && (
                drafted == null ? (
                  <div className="mt-2">
                    <SectionInstructionBox
                      placeholder="Describe the change..."
                      submitLabel="Draft"
                      onSubmit={instruction => handleDraft("skills", instruction)}
                      onCancel={() => setEditing(null)}
                    />
                  </div>
                ) : (
                  <div className="mt-2 space-y-2">
                    <EditableItemForm value={drafted as Record<string, unknown>} onChange={setDrafted} />
                    <div className="flex gap-2">
                      <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                      <button onClick={() => handleConfirmSkillEdit()} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
                    </div>
                  </div>
                )
              )}
            </div>
          ))}
        </div>

        {editing?.section === "skills" && editing.action === "add" ? (
          drafted == null ? (
            <div className="mt-3">
              <SectionInstructionBox
                placeholder="Describe the new skill(s), e.g. 'I learned Kafka and improved my Python'"
                submitLabel="Draft"
                onSubmit={instruction => handleDraft("skills", instruction)}
                onCancel={() => setEditing(null)}
              />
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              {(drafted as { group: string; skill: string }[]).map((draftItem, i) => (
                <div key={i} className="bg-surface rounded-lg p-3">
                  <EditableItemForm
                    value={draftItem}
                    onChange={next => setDrafted((drafted as Record<string, unknown>[]).map((d, j) => (j === i ? next : d)))}
                  />
                </div>
              ))}
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleConfirm("skills")} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        ) : (
          <button
            onClick={() => { setEditing({ section: "skills", action: "add" }); setDrafted(null); }}
            className="mt-3 flex items-center gap-1 text-xs text-accent hover:underline"
          >
            <Plus size={13} /> Add new
          </button>
        )}
      </section>
    );
  }

  async function handleDeleteSkill(group: string, skill: string) {
    if (!slug) return;
    if (!confirm(`Delete "${skill}" from ${group}?`)) return;
    await api.applyResumeSection(slug, "skills", { action: "delete", group, skill });
    loadResume();
  }

  async function handleConfirmSkillEdit() {
    if (!editing || !slug || drafted == null) return;
    await api.applyResumeSection(slug, "skills", {
      action: "edit",
      group: editing.group,
      skill: editing.skill,
      item: drafted,
    });
    setEditing(null);
    setDrafted(null);
    loadResume();
  }
```

- [ ] **Step 2: Add Languages and scalar field rendering**

```typescript
  function renderLanguagesSection() {
    const items = resume?.languages ?? [];
    return (
      <section key="languages">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Languages</h2>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {items.map((lang, i) => (
            <span key={lang} className="flex items-center gap-1 bg-surface border border-gray-200 rounded-full px-2 py-0.5 text-xs text-gray-700">
              {lang}
              <button onClick={() => handleDelete("languages", i)} className="text-gray-400 hover:text-red-500">
                <Trash2 size={11} />
              </button>
            </span>
          ))}
        </div>
        {editing?.section === "languages" && editing.action === "add" ? (
          drafted == null ? (
            <SectionInstructionBox
              placeholder="Describe the new language(s), e.g. 'I learned French and German'"
              submitLabel="Draft"
              onSubmit={instruction => handleDraft("languages", instruction)}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <div className="space-y-2">
              <EditableItemForm value={(drafted as string[]).join("\n")} onChange={v => setDrafted((v as string).split("\n").filter(Boolean))} />
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleConfirm("languages")} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        ) : (
          <button
            onClick={() => { setEditing({ section: "languages", action: "add" }); setDrafted(null); }}
            className="flex items-center gap-1 text-xs text-accent hover:underline"
          >
            <Plus size={13} /> Add new
          </button>
        )}
      </section>
    );
  }

  const SCALAR_FIELDS: { key: string; label: string }[] = [
    { key: "summary", label: "Summary" },
    { key: "designation", label: "Designation" },
    { key: "work_right", label: "Work Right" },
    { key: "email", label: "Email" },
    { key: "phone", label: "Phone" },
    { key: "website", label: "Website" },
  ];

  async function handleScalarConfirm(section: string) {
    if (!slug || drafted == null) return;
    await api.applyResumeSection(slug, section, { action: "edit", item: drafted });
    setEditing(null);
    setDrafted(null);
    loadResume();
  }

  function renderScalarField(fieldKey: string, label: string) {
    const value = String(resume?.[fieldKey] ?? "");
    const isEditingThis = editing?.section === fieldKey;
    return (
      <section key={fieldKey}>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">{label}</h2>
          {!isEditingThis && (
            <button onClick={() => { setEditing({ section: fieldKey, action: "edit" }); setDrafted(null); }} className="text-gray-400 hover:text-gray-700">
              <Pencil size={13} />
            </button>
          )}
        </div>
        {isEditingThis ? (
          drafted == null ? (
            <SectionInstructionBox
              placeholder={`Describe the change to ${label.toLowerCase()}...`}
              submitLabel="Draft"
              onSubmit={instruction => handleDraft(fieldKey, instruction)}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <div className="space-y-2">
              <EditableItemForm value={drafted as string} onChange={setDrafted} />
              <div className="flex gap-2">
                <button onClick={() => { setEditing(null); setDrafted(null); }} className="text-xs text-gray-500 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-gray-50">Cancel</button>
                <button onClick={() => handleScalarConfirm(fieldKey)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">Confirm</button>
              </div>
            </div>
          )
        ) : (
          <p className="text-sm text-gray-700">{value || <span className="text-gray-400">(empty)</span>}</p>
        )}
      </section>
    );
  }
```

Update the section list in the JSX to:

```typescript
      {renderScalarField("summary", "Summary")}
      {renderListObjectSection("experience")}
      {renderSkillsSection()}
      {renderListObjectSection("education")}
      {renderListObjectSection("certifications")}
      {renderLanguagesSection()}
      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">Contact</h2>
        <div className="space-y-3">
          {renderScalarField("designation", "Designation")}
          {renderScalarField("work_right", "Work Right")}
          {renderScalarField("email", "Email")}
          {renderScalarField("phone", "Phone")}
          {renderScalarField("website", "Website")}
        </div>
      </section>
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 4: Manual verification**

With both servers running, open `/profile/rohit/edit`: add a skill, edit a skill (moving it between groups by changing the drafted group name), delete a skill until a group empties and disappears, add/delete a language, and edit the Summary field end-to-end.

- [ ] **Step 5: Commit**

```bash
git add web/app/profile/[slug]/edit/page.tsx
git commit -m "feat: add Skills, Languages, and scalar field editing to the resume edit page"
```

---

### Task 12: History panel — view and restore

**Files:**
- Create: `web/components/resume-edit/HistoryPanel.tsx`
- Modify: `web/app/profile/[slug]/edit/page.tsx`

**Interfaces:**
- Consumes: `api.getResumeHistory`, `api.getResumeVersion`, `api.restoreResumeVersion` (Task 7).

- [ ] **Step 1: Write `HistoryPanel.tsx`**

```typescript
// web/components/resume-edit/HistoryPanel.tsx
"use client";
import { useEffect, useState } from "react";
import { History, Eye, RotateCcw } from "lucide-react";
import * as api from "@/lib/api";
import type { ResumeVersionSummary, ResumeVersion } from "@/lib/types";

interface Props {
  slug: string;
  onRestored: () => void;
}

export function HistoryPanel({ slug, onRestored }: Props) {
  const [open, setOpen] = useState(false);
  const [versions, setVersions] = useState<ResumeVersionSummary[]>([]);
  const [viewing, setViewing] = useState<ResumeVersion | null>(null);

  useEffect(() => {
    if (!open) return;
    api.getResumeHistory(slug).then(setVersions).catch(() => setVersions([]));
  }, [open, slug]);

  async function handleView(versionId: string) {
    const version = await api.getResumeVersion(slug, versionId);
    setViewing(version);
  }

  async function handleRestore(versionId: string) {
    if (!confirm("Restore this version? The current resume will be saved to history first.")) return;
    await api.restoreResumeVersion(slug, versionId);
    setViewing(null);
    setOpen(false);
    onRestored();
  }

  return (
    <div className="border-t border-gray-100 pt-4">
      <button onClick={() => setOpen(o => !o)} className="flex items-center gap-1.5 text-sm font-medium text-gray-700 hover:text-gray-900">
        <History size={15} />
        History {open ? "▲" : "▼"}
      </button>

      {open && (
        <div className="mt-3 space-y-2">
          {versions.length === 0 && <p className="text-xs text-gray-400">No past versions yet.</p>}
          {[...versions].reverse().map(v => (
            <div key={v.id} className="flex items-center justify-between bg-surface rounded-lg px-3 py-2">
              <div>
                <p className="text-xs font-medium text-gray-800">{v.change_summary}</p>
                <p className="text-xs text-gray-400">{new Date(v.timestamp).toLocaleString()}</p>
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => handleView(v.id)} className="text-gray-400 hover:text-gray-700">
                  <Eye size={14} />
                </button>
                <button onClick={() => handleRestore(v.id)} className="text-gray-400 hover:text-accent">
                  <RotateCcw size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {viewing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999]" onClick={() => setViewing(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-xl mx-4 p-6 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-gray-800">{viewing.change_summary}</p>
              <button onClick={() => handleRestore(viewing.id)} className="text-xs bg-accent text-white rounded-lg px-3 py-1.5 hover:bg-accent/90">
                Restore this version
              </button>
            </div>
            <pre className="bg-gray-950 text-green-400 text-xs rounded-lg p-4 overflow-x-auto leading-relaxed">
              {JSON.stringify(viewing.data, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire it into the edit page**

In `web/app/profile/[slug]/edit/page.tsx`, add the import:

```typescript
import { HistoryPanel } from "@/components/resume-edit/HistoryPanel";
```

Add at the bottom of the rendered JSX, just before the closing `</div>` (after the Contact section, before the `showReplace` modal block):

```typescript
      {slug && <HistoryPanel slug={slug} onRestored={loadResume} />}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors

- [ ] **Step 4: Manual verification**

Make a couple of edits on `/profile/rohit/edit`, open the History panel, confirm entries appear with sensible change summaries, click the eye icon to view a past snapshot's raw JSON, then restore an older version and confirm the page reloads with that version's data while the pre-restore state itself now appears as a new history entry.

- [ ] **Step 5: Commit**

```bash
git add web/components/resume-edit/HistoryPanel.tsx web/app/profile/[slug]/edit/page.tsx
git commit -m "feat: add resume version history panel with view and restore"
```

---

## Self-Review Notes

- **Spec coverage:** Data model & storage → Task 1. Full-replace folded into history → Task 2. Backend API (history + apply + draft) → Tasks 3-5. Router mounted → Task 6. Frontend types/API → Task 7. Frontend UI (list-object, skills, languages, scalar, history, Replace Resume moved) → Tasks 8-12. All spec sections have a corresponding task.
- **Type consistency checked:** `SectionApply`/`SectionDraft` field names (`action`, `item_index`, `group`, `skill`, `item`/`instruction`) match `SectionApplyRequest`/`SectionDraftRequest` in `web/lib/types.ts` exactly. `_section_kind`, `SECTION_LABELS`, `TITLE_FIELD`, `FALLBACK_SCHEMA` defined once in Task 4, reused as-is in Task 5 — no renamed duplicates.
- **No placeholders:** every step has complete, runnable code; no "TBD" or "similar to Task N" shortcuts.
