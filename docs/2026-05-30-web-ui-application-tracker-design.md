# Web UI + Application Tracker — Design Spec

**Date:** 2026-05-30  
**Status:** Approved  
**Scope:** Phase 1 — Web UI (resume tailoring), Application Tracker, Multi-profile support, Reliability fixes

---

## Overview

Extend the resume builder with a local web application that supports multiple user profiles, resume tailoring via a browser UI, and a job application tracker. The CLI remains fully functional alongside the web app. The system must be deployable anywhere — locally, on Vercel (Next.js) + a separate Python host, or as two self-hosted processes.

---

## Architecture

Two processes, one project:

```
resume-builder/
├── core/
│   ├── resume_builder.py       # CLI: JSON + template → HTML + PDF
│   ├── resume_template.html    # Jinja2 template (single source of truth)
│   └── config.py               # NEW: shared MODEL constant, HUMANISE_RULES
├── agents/
│   ├── main_agent.py           # CLI orchestrator (unchanged)
│   ├── tailor_agent.py         # AI tailoring + cover letter
│   ├── job_search_agent.py     # Tavily + Claude job search
│   └── linkedin_agent.py       # LinkedIn gap analysis
├── data/
│   └── profiles/
│       └── {slug}/
│           └── resume_data.json
├── output/
│   ├── profiles/
│   │   └── {slug}/
│   │       ├── resumes/        # tailored HTMLs + PDFs
│   │       └── cover_letters/
│   └── jobs/                   # jobs.json, seen_jobs.json
├── tests/                      # NEW: moved from root
│   ├── test_tailor.py
│   ├── test_job_search.py
│   └── test_linkedin.py
├── a2a/
│   └── server.py               # FastAPI (A2A + new REST endpoints)
├── web/                        # NEW: Next.js app
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx            # Dashboard
│   │   ├── tailor/
│   │   │   └── page.tsx
│   │   └── applications/
│   │       └── page.tsx
│   ├── components/
│   ├── lib/
│   │   └── api.ts              # typed API client
│   ├── tailwind.config.ts
│   └── package.json
├── requirements.txt
└── README.md
```

**Next.js** (`web/`) runs on port 3000. Calls FastAPI at `http://localhost:8000` by default, configurable via `NEXT_PUBLIC_API_URL` env var (e.g. set to a Railway URL for production).

**FastAPI** (`a2a/server.py`) runs on port 8000. Extends the existing A2A server with new REST endpoints.

**CLI** — all existing commands work unchanged. A `--profile <slug>` flag is added to scope operations to a profile. Defaults to the first profile if only one exists.

---

## Data Model

### Profiles

Stored as directories under `data/profiles/{slug}/`. No database table needed — the filesystem is the source of truth.

```
data/profiles/rohit/resume_data.json
data/profiles/priya/resume_data.json
```

Profile metadata (name, slug, created_at) stored in `data/profiles/profiles.json`:

```json
[
  { "id": "uuid", "name": "Rohit", "slug": "rohit", "created_at": "2026-05-30T..." },
  { "id": "uuid", "name": "Priya", "slug": "priya", "created_at": "2026-05-30T..." }
]
```

Slug generation: lowercase, spaces replaced with hyphens, non-alphanumeric characters stripped (e.g. "Priya Mopuri" → `priya-mopuri`). Slugs must be unique — if a collision occurs, the API returns a 409 with a suggested alternative. Slugs are immutable after creation.

### Applications (SQLite)

Single `applications` table in `data/applications.db`:

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | UUID |
| `profile_id` | TEXT | Soft reference to profile slug (not enforced — profiles.json is the source of truth) |
| `job_title` | TEXT | |
| `company` | TEXT | |
| `location` | TEXT | |
| `url` | TEXT | nullable |
| `status` | TEXT | `saved`, `applied`, `interview`, `offer`, `rejected` |
| `applied_date` | TEXT | ISO date, nullable |
| `notes` | TEXT | nullable |
| `resume_file` | TEXT | path to tailored PDF, nullable |
| `cover_letter_file` | TEXT | path to cover letter, nullable |
| `created_at` | TEXT | ISO datetime |
| `updated_at` | TEXT | ISO datetime |

### Tailor Job State (in-memory)

Tailoring runs are transient. Stored in a dict in the FastAPI process (`Dict[str, TailorJob]`). Not persisted — if the server restarts, in-progress jobs are lost (acceptable: user retriggers).

```python
TailorJob {
  id: str           # uuid
  profile_slug: str
  status: "running" | "completed" | "failed"
  message: str      # latest progress line
  pdf_file: str     # path, set on completion
  cover_letter_file: str
  error: str        # set on failure
}
```

---

## Backend API

All endpoints under `/api/`. CORS enabled for `http://localhost:3000`.

### Profiles

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/profiles` | List all profiles |
| `POST` | `/api/profiles` | Create profile (name + slug) |
| `PATCH` | `/api/profiles/{slug}` | Update profile name |
| `DELETE` | `/api/profiles/{slug}` | Delete profile and all its data |
| `POST` | `/api/profiles/{slug}/resume/parse` | Upload PDF/DOCX → Claude parses → stores result in server-side temp dict keyed by slug → returns extracted JSON preview |
| `POST` | `/api/profiles/{slug}/resume/confirm` | Moves the temp parsed JSON to `data/profiles/{slug}/resume_data.json` and clears the temp entry |
| `GET` | `/api/profiles/{slug}/resume` | Return current resume_data.json |

### Tailoring

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/tailor` | Start tailoring job `{ profile_slug, url? , jd_text? }` → returns `{ job_id }` |
| `GET` | `/api/tailor/{job_id}` | Poll status: `{ status, message, pdf_file?, cover_letter_file?, error? }` |
| `GET` | `/api/tailor/{job_id}/pdf` | Stream PDF for download |
| `GET` | `/api/tailor/{job_id}/cover-letter` | Stream cover letter for download |

### Applications

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/applications?profile={slug}` | List applications for a profile |
| `POST` | `/api/applications` | Create application |
| `PATCH` | `/api/applications/{id}` | Update any field (status, notes, etc.) |
| `DELETE` | `/api/applications/{id}` | Delete application |

---

## Frontend

**Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, `dnd-kit` (drag and drop).

**Colour palette:** Dark navy `#1a2744` (sidebar, header), white content area, blue-purple accent `#5b6ef5` for CTAs and active states, light grey `#f5f6fa` for card backgrounds. Inter font.

### Pages

**`/` — Dashboard**
- Stats bar: total applications, interviews, offers
- Recent 5 applications with status badges
- "Tailor a Resume" CTA button
- Active profile shown in sidebar

**`/tailor` — Resume Tailoring**
- Tab toggle: "Job URL" / "Paste JD"
- Submit button triggers `POST /api/tailor`
- Progress section: polls every 2s, shows latest message
- On completion: "Download PDF" and "Download Cover Letter" buttons
- Option to add the job to the Application Tracker on completion — pre-fills company, role, and URL from the tailoring job; status defaults to `applied`

**`/applications` — Application Tracker**
- Toggle in top-right: Table / Kanban
- **Table view:** columns — Company, Role, Location, Status, Applied Date, Actions (edit, delete). Sortable by any column. Click row to open edit modal.
- **Kanban view:** columns — Saved, Applied, Interview, Offer, Rejected. Drag card to change status (calls `PATCH /api/applications/{id}`). Cards show company + role + applied date.
- "+ Add Application" button opens a modal form (company, role, location, URL, status, notes).

### Profile Switcher

Sits in the top-left of the sidebar. Shows current profile's initial in a coloured circle (e.g. "R"). Click to open a dropdown:
- List of profiles — click to switch
- "+ Add Profile" — opens the add profile modal

**Add Profile modal:**
1. Enter name
2. Upload resume PDF or DOCX
3. "Parse Resume" → calls `POST /api/profiles/{slug}/resume/parse`
4. Shows extracted fields (name, summary, experience, skills, education, certifications) as a read-only preview
5. "Confirm & Save" → calls `POST /api/profiles/{slug}/resume/confirm`

**View Current Resume Data:**
The profile switcher dropdown includes a "View Resume Data" link that opens `/profile/{slug}` — a read-only page showing the stored `resume_data.json` rendered as readable cards (name, summary, experience list, skills, education, certifications). Not raw JSON.

---

## Reliability Fixes (bundled)

These land in the same implementation cycle:

| Issue | Fix |
|---|---|
| `tailor_agent.py` calls `resume_builder.py` via `subprocess` | Import and call `render_resume()` directly |
| JSON parsed with `find("{")` / `rfind("}")` in `tailor_agent.py` and `job_search_agent.py` | Replace with a proper extraction helper in `core/config.py` |
| `MODEL = "claude-sonnet-4-6"` hardcoded in 3 agent files | Move to `core/config.py` as `DEFAULT_MODEL` |
| `HUMANISE_RULES` only in `tailor_agent.py` (duplicated in `a2a/skills/tailor.py`) | Consolidate to `core/config.py` |
| Base resume PDFs/HTMLs generated into root dir | Output to `output/` |
| `test_*.py` in root dir | Move to `tests/` |

---

## CLI Changes

All existing commands unchanged. New `--profile <slug>` flag added:

```bash
python3 agents/main_agent.py --tailor <url> --profile rohit
python3 agents/main_agent.py --jobs-only --profile priya
```

If `--profile` is omitted and only one profile exists, it uses that profile. If multiple profiles exist and none is specified, it errors with a helpful message.

---

## Out of Scope (This Phase)

- Authentication / login
- Auto-apply (LinkedIn Easy Apply — deferred to a future phase)
- Job search via web UI (CLI only for now)
- LinkedIn comparison via web UI (CLI only for now)
- Multiple resume templates
- Resume editing via UI (re-upload to update)
