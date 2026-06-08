# Tailor Resume — Edit Page Design

**Date:** 2026-06-08
**Status:** Approved

## Problem

The tailor flow produces a resume JSON, PDF, and cover letter — but gives no way to correct inaccuracies. The AI occasionally overstates scope or attributes the wrong work. There is currently no frontend path to fix this.

## Decision

Inline editing on a dedicated `/tailor/[job_id]/edit` page. Direct textarea editing — no LLM involved in corrections. Zero extra API tokens per edit.

## User Flow

1. User submits URL or JD on `/tailor`
2. Tailoring completes — existing buttons (Download PDF, Cover Letter, Add to Tracker) remain
3. New **"Edit Resume"** button added to the completed state
4. Click → navigate to `/tailor/[job_id]/edit`
5. User edits summary, experience bullets, and/or cover letter inline
6. Click **"Save & Regenerate PDF"**
7. Backend writes updated JSON to disk, calls `render_resume()` directly (no LLM)
8. Redirect to `/tailor?job=[job_id]` — tailor page restores completed state from backend, showing Download PDF + Add to Tracker

## Edit Page Layout (`/tailor/[job_id]/edit`)

- **Header row:** "Edit Tailored Resume" title + subtitle noting base profile is unchanged. "Back without saving" link top-right.
- **Summary:** Single textarea, pre-filled with tailored summary.
- **Experience:** One card per job. Most recent job expanded by default, rest collapsed (show title + bullet count, click to expand). Each bullet is its own textarea — resizes to content.
- **Cover Letter:** Single large textarea, pre-filled with the tailored cover letter text.
- **Footer:** "Back without saving" (text link) + "Save & Regenerate PDF" (primary button), right-aligned.

## What Changes vs. Today

### Backend — `a2a/routes/tailor_api.py`

- `GET /api/tailor/{job_id}` — add `json_file` to the response (currently stored in `_jobs` but not returned)
- `GET /api/tailor/{job_id}/data` — new endpoint: reads and returns the tailored JSON file as JSON
- `GET /api/tailor/{job_id}/cover-letter-text` — new endpoint: reads and returns cover letter as plain text (existing `/cover-letter` returns a file download)
- `PATCH /api/tailor/{job_id}/data` — new endpoint: accepts updated resume JSON body, writes it to `json_file` on disk, calls `render_resume()` to regenerate the PDF, optionally accepts updated cover letter text and writes that too

### Frontend

- `web/lib/types.ts` — extend `TailorJob` to include `json_file?: string`
- `web/lib/api.ts` — add `getTailorData(jobId)`, `getTailorCoverLetterText(jobId)`, `patchTailorData(jobId, resumeJson, coverLetter)`
- `web/app/tailor/page.tsx` — add "Edit Resume" button in the completed state; read `?job=[job_id]` query param on mount to restore completed state
- `web/app/tailor/[job_id]/edit/page.tsx` — new page (see layout above)
- `web/components/TopNav.tsx` — no change needed (edit page is a sub-route of tailor, not a top-level nav item)

## Constraints

- Edits only affect the tailored output files (`output/profiles/{slug}/resumes/resume_data_{slug}.json` and the PDF). The base profile at `data/profiles/{slug}/resume_data.json` is never touched.
- No LLM calls on save. `render_resume()` is called directly — same path as the original tailor agent.
- The `_jobs` dict is in-memory. If the server restarts between tailoring and editing, the edit page will 404. Acceptable for now — this is a session-scoped tool, not a persistence system.

## Out of Scope

- AI-assisted rewrites (no "rewrite this bullet" button)
- Editing skills sections (skills are rarely hallucinated; add later if needed)
- Persisting edit history or diffs
- Editing education or certifications (these are never changed by the tailor agent)
