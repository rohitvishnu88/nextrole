# Tailor Resume Edit Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/tailor/[job_id]/edit` page where users can inline-edit the summary, experience bullets, and cover letter of a tailored resume, then regenerate the PDF with zero LLM calls.

**Architecture:** Three new backend endpoints expose and mutate the tailored JSON and cover letter on disk. A new Next.js dynamic-route page fetches, renders, and PATCHes that data. The tailor page gains an "Edit Resume" button and restores completed state from a `?job=` query param on redirect back.

**Tech Stack:** FastAPI (Python 3.9), pytest + FastAPI TestClient, Next.js 14 App Router (TypeScript), Tailwind CSS, `render_resume()` from `core/resume_builder.py`

---

## File Map

| File | Change |
|---|---|
| `a2a/routes/tailor_api.py` | Add module-level `render_resume` import; extend GET status response; add 3 new endpoints |
| `tests/test_tailor_edit_api.py` | New — pytest tests for the 4 backend endpoints |
| `web/lib/types.ts` | Extend `TailorJob`; add `TailoredExperience`, `TailoredResume` |
| `web/lib/api.ts` | Add `getTailorData`, `getTailorCoverLetterText`, `patchTailorData` |
| `web/app/tailor/page.tsx` | Add "Edit Resume" button; restore state from `?job=` query param |
| `web/app/tailor/[job_id]/edit/page.tsx` | New — inline edit page |

---

## Task 1: Backend — add render_resume import to tailor_api.py

**Why:** Right now `tailor_api.py` has no access to `render_resume()`. The new PATCH endpoint needs it to regenerate the PDF after edits. We add the import at module level so it's available throughout the file.

**Files:**
- Modify: `a2a/routes/tailor_api.py`

- [ ] **Step 1: Add sys and render_resume imports at the top of tailor_api.py**

Open `a2a/routes/tailor_api.py`. After the existing imports, add:

```python
import sys
from pathlib import Path

# Make core/ importable so we can call render_resume directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
from resume_builder import render_resume
```

The file already imports `Path` — don't duplicate that. The final import block should look like:

```python
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
from resume_builder import render_resume
```

- [ ] **Step 2: Verify the server still starts cleanly**

```bash
python3 -m uvicorn a2a.server:app --port 8000 --reload
```

Expected: no import errors. Stop with Ctrl-C.

- [ ] **Step 3: Commit**

```bash
git add a2a/routes/tailor_api.py
git commit -m "feat: import render_resume into tailor_api for PDF regeneration"
```

---

## Task 2: Backend — expose json_file in the GET status response

**Why:** The frontend currently has no way to know the path of the tailored JSON file. The edit page needs the `job_id` to fetch data; the backend can now serve that data through new endpoints. But first, the status response should confirm `json_file` is set (useful for debugging and for the edit button to know whether data exists).

**Files:**
- Modify: `a2a/routes/tailor_api.py`
- Test: `tests/test_tailor_edit_api.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_tailor_edit_api.py`:

```python
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

    # html path mirrors what the tailor agent produces
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
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_status_includes_json_file -v
```

Expected: FAIL — `json_file` key is missing from the response.

- [ ] **Step 3: Update GET /{job_id} to return json_file**

In `a2a/routes/tailor_api.py`, update the `get_tailor_status` function:

```python
@router.get("/{job_id}")
def get_tailor_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "message": job.get("message", ""),
        "pdf_file": job.get("pdf_file"),
        "cover_letter_file": job.get("cover_letter_file"),
        "json_file": job.get("json_file"),
        "url": job.get("url", ""),
    }
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_status_includes_json_file -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/tailor_api.py tests/test_tailor_edit_api.py
git commit -m "feat: expose json_file in tailor status response"
```

---

## Task 3: Backend — GET /api/tailor/{job_id}/data

**Why:** The edit page needs to load the tailored resume JSON so it can populate the textareas. This endpoint reads the file from disk (already written by the tailor agent) and returns it as JSON.

**Files:**
- Modify: `a2a/routes/tailor_api.py`
- Test: `tests/test_tailor_edit_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tailor_edit_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_get_data_returns_resume_json tests/test_tailor_edit_api.py::test_get_data_404_for_unknown_job -v
```

Expected: FAIL — endpoint doesn't exist yet.

- [ ] **Step 3: Add the GET /data endpoint**

In `a2a/routes/tailor_api.py`, add after `get_tailor_status`:

```python
@router.get("/{job_id}/data")
def get_tailor_data(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    json_path = Path(job["json_file"])
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Resume JSON not found on disk")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)
```

Note: FastAPI automatically serialises the returned dict as JSON. No need to wrap in `JSONResponse`.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_get_data_returns_resume_json tests/test_tailor_edit_api.py::test_get_data_404_for_unknown_job -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/tailor_api.py tests/test_tailor_edit_api.py
git commit -m "feat: add GET /api/tailor/{job_id}/data endpoint"
```

---

## Task 4: Backend — GET /api/tailor/{job_id}/cover-letter-text

**Why:** The existing `/cover-letter` endpoint returns a file download (`FileResponse`). The edit page needs the raw text in a JSON field so it can prefill a textarea. We add a separate endpoint for this.

**Files:**
- Modify: `a2a/routes/tailor_api.py`
- Test: `tests/test_tailor_edit_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tailor_edit_api.py`:

```python
def test_get_cover_letter_text(client):
    c, mod = client
    resp = c.get("/api/tailor/test-job-id/cover-letter-text")
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Cover letter text."
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_get_cover_letter_text -v
```

Expected: FAIL.

- [ ] **Step 3: Add the endpoint**

In `a2a/routes/tailor_api.py`, add after `get_tailor_data`:

```python
@router.get("/{job_id}/cover-letter-text")
def get_cover_letter_text(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    path = Path(job["cover_letter_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter not found on disk")
    return {"text": path.read_text(encoding="utf-8")}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_get_cover_letter_text -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/tailor_api.py tests/test_tailor_edit_api.py
git commit -m "feat: add GET /api/tailor/{job_id}/cover-letter-text endpoint"
```

---

## Task 5: Backend — PATCH /api/tailor/{job_id}/data

**Why:** This is the save action. The frontend sends the full edited resume JSON (and optionally the cover letter text). The endpoint writes the JSON to the same file the tailor agent originally produced, regenerates the PDF by calling `render_resume()` directly, and optionally overwrites the cover letter file.

**Files:**
- Modify: `a2a/routes/tailor_api.py`
- Test: `tests/test_tailor_edit_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tailor_edit_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_tailor_edit_api.py::test_patch_data_updates_json_and_cover_letter tests/test_tailor_edit_api.py::test_patch_data_404_for_unknown_job -v
```

Expected: FAIL — endpoint doesn't exist.

- [ ] **Step 3: Add the Pydantic model and PATCH endpoint**

In `a2a/routes/tailor_api.py`, add the request model near the other models at the top:

```python
class UpdateRequest(BaseModel):
    resume: dict
    cover_letter: Optional[str] = None
```

Then add the endpoint after `get_cover_letter_text`:

```python
@router.patch("/{job_id}/data")
def update_tailor_data(job_id: str, body: UpdateRequest):
    job = _jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")

    json_path = Path(job["json_file"])
    pdf_path = Path(job["pdf_file"])
    # The HTML file has the same stem as the PDF — render_resume needs both paths
    html_path = pdf_path.with_suffix(".html")

    # Write updated JSON to disk
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(body.resume, f, indent=2)

    # Regenerate PDF — same call the tailor agent makes
    render_resume(body.resume, str(html_path), str(pdf_path))

    # Overwrite cover letter if provided
    if body.cover_letter is not None:
        Path(job["cover_letter_file"]).write_text(body.cover_letter, encoding="utf-8")

    return {"ok": True}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_tailor_edit_api.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
python3 -m pytest tests/ -v --ignore=tests/test_tailor.py --ignore=tests/test_job_search.py --ignore=tests/test_linkedin.py
```

(Those three excluded files are manual runners that need live API keys, not pytest suites.)

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add a2a/routes/tailor_api.py tests/test_tailor_edit_api.py
git commit -m "feat: add PATCH /api/tailor/{job_id}/data endpoint for resume editing"
```

---

## Task 6: Frontend — extend types and API client

**Why:** TypeScript types define the contract between the frontend and backend. Adding them before the UI means the compiler will catch mismatches as we build the edit page. The API functions wrap `fetch` calls — one place to change if an endpoint URL ever moves.

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`

- [ ] **Step 1: Extend TailorJob and add resume types in types.ts**

Open `web/lib/types.ts`. Add `json_file` to `TailorJob`, and append the two new interfaces:

```typescript
export interface TailorJob {
  job_id: string;
  status: "running" | "completed" | "failed";
  message: string;
  pdf_file?: string;
  cover_letter_file?: string;
  json_file?: string;   // ← add this line
  url?: string;
}

export interface TailoredExperience {
  title: string;
  highlight: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  description: string[];
}

export interface TailoredResume {
  name: string;
  designation: string;
  work_right?: string;
  email: string;
  phone: string;
  website?: string;
  summary: string;
  experience: TailoredExperience[];
  // skills, education, certifications are preserved but not shown in the editor
  [key: string]: unknown;
}
```

The `[key: string]: unknown` index signature lets TypeScript know there are more fields we don't explicitly type — they'll be preserved when we PATCH back.

- [ ] **Step 2: Add three API functions in api.ts**

Open `web/lib/api.ts`. Add after the existing tailor functions:

```typescript
export const getTailorData = (jobId: string) =>
  req<TailoredResume>(`/tailor/${jobId}/data`);

export const getTailorCoverLetterText = (jobId: string) =>
  req<{ text: string }>(`/tailor/${jobId}/cover-letter-text`);

export const patchTailorData = (
  jobId: string,
  resume: TailoredResume,
  coverLetter: string,
) =>
  req<{ ok: boolean }>(`/tailor/${jobId}/data`, {
    method: "PATCH",
    body: JSON.stringify({ resume, cover_letter: coverLetter }),
  });
```

Add the `TailoredResume` import at the top of the file — update the existing import line:

```typescript
import type { Application, ApplicationStatus, Profile, TailorJob, TailoredResume, SearchBrief, Signal } from "./types";
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd web && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/lib/types.ts web/lib/api.ts
git commit -m "feat: add TailoredResume types and tailor edit API functions"
```

---

## Task 7: Frontend — add "Edit Resume" button and restore state from ?job= param

**Why:** Two changes to the existing tailor page. First, the "Edit Resume" button appears once tailoring completes — it links to `/tailor/[job_id]/edit`. Second, after the user saves on the edit page they're redirected back to `/tailor?job=[job_id]`; the page needs to restore the completed job state from that query param so the download + tracker buttons reappear.

**Files:**
- Modify: `web/app/tailor/page.tsx`

- [ ] **Step 1: Update tailor/page.tsx**

Replace the full contents of `web/app/tailor/page.tsx` with:

```tsx
"use client";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import * as api from "@/lib/api";
import type { TailorJob } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { AddApplicationModal } from "@/components/AddApplicationModal";
import { Wand2, Download, Plus, Pencil } from "lucide-react";

function TailorPageInner() {
  const profile = useActiveProfile();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<"url" | "jd">("url");
  const [input, setInput] = useState("");
  const [job, setJob] = useState<TailorJob | null>(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [showAddToTracker, setShowAddToTracker] = useState(false);

  // Restore completed job when redirected back from the edit page
  useEffect(() => {
    const jobParam = searchParams.get("job");
    if (!jobParam || job) return;
    api.getTailorStatus(jobParam).then(setJob).catch(() => {});
  }, [searchParams, job]);

  async function handleSubmit() {
    if (!input.trim() || !profile) return;
    setError("");
    setJob(null);
    try {
      const res = await api.startTailor(
        profile,
        mode === "url" ? input.trim() : undefined,
        mode === "jd" ? input.trim() : undefined,
      );
      setJob({ job_id: res.job_id, status: "running", message: "Starting..." });
      setPolling(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start");
    }
  }

  useEffect(() => {
    if (!polling || !job) return;
    const interval = setInterval(async () => {
      try {
        const status = await api.getTailorStatus(job.job_id);
        setJob(status);
        if (status.status !== "running") setPolling(false);
      } catch {
        setPolling(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [polling, job]);

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy">Tailor a Resume</h1>
        <p className="text-sm text-muted mt-1">Paste a job URL or description — get a tailored PDF and cover letter</p>
      </div>

      {!profile && (
        <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
          Select or create a profile first from the top-right.
        </div>
      )}

      <div className="bg-white rounded-2xl border border-warm-border p-6 space-y-4">
        <div className="flex gap-2">
          {(["url", "jd"] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setInput(""); }}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                mode === m
                  ? "bg-accent text-white"
                  : "bg-cream text-muted hover:text-navy"
              }`}
            >
              {m === "url" ? "Job URL" : "Paste JD"}
            </button>
          ))}
        </div>

        {mode === "url" ? (
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="https://linkedin.com/jobs/view/..."
            className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy placeholder-muted bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition"
          />
        ) : (
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={8}
            className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy placeholder-muted bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-none"
          />
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={!input.trim() || !profile || polling}
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors"
        >
          <Wand2 size={15} />
          {polling ? "Working…" : "Tailor Resume"}
        </button>
      </div>

      {job && (
        <div className="bg-white rounded-2xl border border-warm-border p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${
              job.status === "running" ? "bg-yellow-400 animate-pulse" :
              job.status === "completed" ? "bg-green-500" : "bg-red-400"
            }`} />
            <p className="text-sm font-medium text-navy">{job.message}</p>
          </div>

          {job.status === "completed" && (
            <div className="flex flex-wrap gap-2 pt-1">
              <a
                href={`/api/tailor/${job.job_id}/pdf`}
                download
                className="flex items-center gap-2 bg-navy hover:bg-navy/90 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                Download PDF
              </a>
              <a
                href={`/api/tailor/${job.job_id}/cover-letter`}
                download
                className="flex items-center gap-2 border border-warm-border text-navy hover:bg-cream rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Download size={14} />
                Cover Letter
              </a>
              <a
                href={`/tailor/${job.job_id}/edit`}
                className="flex items-center gap-2 border border-warm-border text-navy hover:bg-cream rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Pencil size={14} />
                Edit Resume
              </a>
              <button
                onClick={() => setShowAddToTracker(true)}
                className="flex items-center gap-2 border border-accent text-accent hover:bg-accent-light rounded-xl px-4 py-2 text-sm font-medium transition-colors"
              >
                <Plus size={14} />
                Add to Tracker
              </button>
            </div>
          )}
        </div>
      )}

      {showAddToTracker && profile && (
        <AddApplicationModal
          profileId={profile}
          prefillUrl={job?.url}
          onClose={() => setShowAddToTracker(false)}
          onCreated={() => setShowAddToTracker(false)}
        />
      )}
    </div>
  );
}

// useSearchParams() requires a Suspense boundary in Next.js App Router
export default function TailorPage() {
  return (
    <Suspense fallback={null}>
      <TailorPageInner />
    </Suspense>
  );
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd web && npm run typecheck
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/app/tailor/page.tsx
git commit -m "feat: add Edit Resume button and restore job state from ?job= param"
```

---

## Task 8: Frontend — new edit page /tailor/[job_id]/edit

**Why:** This is the main deliverable. It fetches the tailored JSON and cover letter, renders them as editable textareas (summary, per-job bullets, cover letter), and PATCHes the changes on save before redirecting back to the tailor page.

**Files:**
- Create: `web/app/tailor/[job_id]/edit/page.tsx`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p web/app/tailor/\[job_id\]/edit
```

- [ ] **Step 2: Create the edit page**

Create `web/app/tailor/[job_id]/edit/page.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import * as api from "@/lib/api";
import type { TailoredResume } from "@/lib/types";
import { Save, ChevronDown, ChevronRight } from "lucide-react";

export default function EditTailorPage() {
  const { job_id } = useParams<{ job_id: string }>();
  const router = useRouter();

  const [resume, setResume] = useState<TailoredResume | null>(null);
  const [coverLetter, setCoverLetter] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0]));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getTailorData(job_id),
      api.getTailorCoverLetterText(job_id),
    ])
      .then(([resumeData, clData]) => {
        setResume(resumeData);
        setCoverLetter(clData.text);
      })
      .catch(() => setError("Failed to load tailored resume."))
      .finally(() => setLoading(false));
  }, [job_id]);

  function updateSummary(value: string) {
    setResume(prev => prev ? { ...prev, summary: value } : prev);
  }

  function updateBullet(expIdx: number, bulletIdx: number, value: string) {
    setResume(prev => {
      if (!prev) return prev;
      const experience = prev.experience.map((exp, i) =>
        i === expIdx
          ? {
              ...exp,
              description: exp.description.map((b, j) =>
                j === bulletIdx ? value : b
              ),
            }
          : exp
      );
      return { ...prev, experience };
    });
  }

  function toggleExpand(idx: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  async function handleSave() {
    if (!resume) return;
    setSaving(true);
    setError("");
    try {
      await api.patchTailorData(job_id, resume, coverLetter);
      router.push(`/tailor?job=${job_id}`);
    } catch {
      setError("Failed to save. Please try again.");
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl">
        <p className="text-sm text-muted animate-pulse">Loading tailored resume…</p>
      </div>
    );
  }

  if (error && !resume) {
    return (
      <div className="max-w-3xl">
        <p className="text-sm text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-4 pb-16">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Edit Tailored Resume</h1>
          <p className="text-sm text-muted mt-1">
            Changes only affect this tailored version — your base profile is unchanged
          </p>
        </div>
        <button
          onClick={() => router.back()}
          className="text-sm text-muted hover:text-navy transition-colors mt-1"
        >
          ← Back without saving
        </button>
      </div>

      {/* Summary */}
      <div className="bg-white rounded-2xl border border-warm-border p-5 space-y-2">
        <p className="text-xs font-semibold text-muted uppercase tracking-wide">Summary</p>
        <textarea
          value={resume?.summary ?? ""}
          onChange={e => updateSummary(e.target.value)}
          rows={4}
          className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-y"
        />
      </div>

      {/* Experience */}
      {resume?.experience.map((exp, expIdx) => (
        <div key={expIdx} className="bg-white rounded-2xl border border-warm-border overflow-hidden">
          {/* Job header — always visible, click to expand/collapse */}
          <button
            onClick={() => toggleExpand(expIdx)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-cream transition-colors text-left"
          >
            <div>
              <p className="text-sm font-semibold text-navy">{exp.title}</p>
              <p className="text-xs text-muted mt-0.5">
                {exp.company}{exp.highlight ? ` — ${exp.highlight}` : ""} · {exp.start_date} – {exp.end_date}
                {!expanded.has(expIdx) && (
                  <span className="ml-2 text-muted">· {exp.description.length} bullets</span>
                )}
              </p>
            </div>
            {expanded.has(expIdx)
              ? <ChevronDown size={16} className="text-muted shrink-0" />
              : <ChevronRight size={16} className="text-muted shrink-0" />
            }
          </button>

          {/* Bullets — only shown when expanded */}
          {expanded.has(expIdx) && (
            <div className="px-5 pb-5 space-y-2">
              {exp.description.map((bullet, bulletIdx) => (
                <div key={bulletIdx} className="flex gap-3 items-start">
                  <span className="text-muted mt-2.5 text-base leading-none shrink-0">•</span>
                  <textarea
                    value={bullet}
                    onChange={e => updateBullet(expIdx, bulletIdx, e.target.value)}
                    rows={2}
                    className="flex-1 border border-warm-border rounded-xl px-3 py-2 text-sm text-navy bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-y"
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Cover Letter */}
      <div className="bg-white rounded-2xl border border-warm-border p-5 space-y-2">
        <p className="text-xs font-semibold text-muted uppercase tracking-wide">Cover Letter</p>
        <textarea
          value={coverLetter}
          onChange={e => setCoverLetter(e.target.value)}
          rows={10}
          className="w-full border border-warm-border rounded-xl px-4 py-2.5 text-sm text-navy bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent transition resize-y"
        />
      </div>

      {/* Save actions */}
      {error && <p className="text-sm text-red-500">{error}</p>}
      <div className="flex items-center justify-end gap-4">
        <button
          onClick={() => router.back()}
          className="text-sm text-muted hover:text-navy transition-colors"
        >
          ← Back without saving
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-navy hover:bg-navy/90 disabled:opacity-50 text-white rounded-xl px-5 py-2.5 text-sm font-semibold transition-colors"
        >
          <Save size={15} />
          {saving ? "Saving…" : "Save & Regenerate PDF"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd web && npm run typecheck
```

Expected: no errors.

- [ ] **Step 4: Start both servers and test the full flow manually**

Terminal 1:
```bash
python3 -m uvicorn a2a.server:app --port 8000 --reload
```

Terminal 2:
```bash
cd web && npm run dev
```

Then:
1. Open http://localhost:3000/tailor
2. Select the rohit profile, paste a job URL, click "Tailor Resume"
3. Wait for completion — confirm "Edit Resume" button appears alongside Download
4. Click "Edit Resume" — confirm `/tailor/[job_id]/edit` loads with summary and experience
5. Edit a bullet (change some text)
6. Click "Save & Regenerate PDF" — confirm redirect to `/tailor?job=[id]`
7. Confirm the completed job state is restored (all buttons visible)
8. Download the PDF — confirm the edited text appears in it

- [ ] **Step 5: Commit**

```bash
git add web/app/tailor/
git commit -m "feat: add /tailor/[job_id]/edit inline resume editing page"
```

---

## Self-Review

**Spec coverage:**
- ✅ Inline editing for summary, bullets, cover letter
- ✅ New `/tailor/[job_id]/edit` page
- ✅ "Edit Resume" button on completed state
- ✅ Redirect back to `/tailor?job=[id]` after save
- ✅ Zero LLM calls on save — `render_resume()` only
- ✅ Base profile untouched — edits go to `output/` not `data/`
- ✅ Skills, education, certifications preserved (not shown, not modified)
- ✅ Collapsible experience sections, first expanded by default

**No placeholders:** all steps have complete code.

**Type consistency:** `TailoredResume` defined in Task 6, used in Task 7 (api.ts import) and Task 8 (edit page). `patchTailorData` signature matches `UpdateRequest` Pydantic model.

**One gap noted:** The `test_patch_data_updates_json_and_cover_letter` test uses `monkeypatch.setattr(resume_builder, ...)` which requires `resume_builder` to be importable in the test environment. This works because Task 1 adds `sys.path.insert` at module level in `tailor_api.py`, and the test file adds the same path insert. If Playwright is not installed, `import resume_builder` at module level will fail unless `playwright` is a dev dependency. Verify with `python3 -c "import resume_builder"` before running tests.
