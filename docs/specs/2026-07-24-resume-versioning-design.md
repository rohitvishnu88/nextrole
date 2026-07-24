# Resume Versioning & AI Section Editing — Design Spec

**Goal:** Let the user update their base resume over time (add a recent project, note new skills learned, correct an existing entry) without re-uploading and re-parsing a whole document, via an AI-assisted per-section editor. Every change — including the existing full-file replace flow — is versioned, capped at the last 20 states, with restore support.

**Problem today:** `resume_data.json` is a single flat file per profile, overwritten wholesale whenever a new resume file is parsed and confirmed (`a2a/routes/profiles.py::confirm_resume`). There is no history and no way to touch a single section without re-uploading and re-parsing an entire document.

---

## 1. Data model & storage

```
data/profiles/{slug}/
  resume_data.json       # current version — unchanged shape, still the single source of truth every other part of the app reads
  resume_history.json    # {"versions": [{id, timestamp, change_summary, data}, ...]}, oldest → newest, capped at 20
```

- Every confirmed mutation — a section add/edit/delete, a restore, or a full-file replace via the existing parse/confirm flow — first pushes the **current** `resume_data.json` into `resume_history.json` (with an auto-generated `change_summary`), then writes the new state as the current `resume_data.json`.
- If `resume_history.json` already holds 20 entries, the oldest is dropped before appending (FIFO, `versions[-20:]` after append).
- Restoring a past version pushes the current state to history first (so restoring never loses anything), then writes the restored version's `data` as the new `resume_data.json`.
- `change_summary` is generated deterministically, not via another AI call — e.g. `"Added Experience: <title>"`, `"Edited Skills: Cloud"`, `"Deleted Certifications: <name>"`, `"Replaced via file upload"`, `"Restored version from <timestamp>"`.

**Why a single capped-array file over a `history/` directory of per-version files:** matches the existing "one JSON file per concern per profile" pattern (`resume_data.json`, `search_brief.json`). No directory listing, filename/timestamp bookkeeping, or separate prune-old-files step — just read, append/slice, write. Capped at 20 snapshots of a few KB each, total size stays trivial. A diff/patch-based history would be more storage-efficient but is unwarranted complexity at this scale (a single-user, file-based tool).

## 2. Section shapes

Four distinct edit behaviours across `resume_data.json`'s fields:

| Kind | Sections | Item |
|---|---|---|
| List-of-objects | `experience`, `education`, `certifications` | one object (e.g. title/company/dates/description) |
| Flat list | `languages` | one string |
| Grouped list | `skills` | `{group, skill}` — adding to a group name that doesn't exist creates it; deleting the last skill in a group removes the now-empty group |
| Scalar | `name`, `designation`, `work_right`, `email`, `phone`, `website`, `summary` | the field's whole value — only `action: "edit"` is valid, no add/delete |

## 3. Backend API

New router: `a2a/routes/resume_versions.py` (kept separate from `a2a/routes/profiles.py`, which already mixes profile CRUD with resume parsing — this avoids growing that file further). Mounted in `a2a/server.py` alongside the existing routers.

All endpoints under `/api/profiles/{slug}/resume/...`:

| Endpoint | Behaviour |
|---|---|
| `GET /history` | List past versions: `{id, timestamp, change_summary}` only — no full `data`, keeps the list cheap to fetch |
| `GET /history/{version_id}` | Full snapshot of one past version, for viewing before restoring |
| `POST /history/{version_id}/restore` | Push current state to history, then make this past version current |
| `POST /sections/{section}/draft` | Body: `{action: "add"\|"edit", item_index?, instruction}` → Claude drafts the item(s)/value. **Not saved** — returned to the frontend for the editable preview |
| `POST /sections/{section}/apply` | Body: `{action: "add"\|"edit"\|"delete", item_index?, item?}` → pushes a history snapshot, applies the change, saves `resume_data.json`. `delete` takes no AI call — direct removal |

The existing `POST /resume/confirm` (full file-upload replace, in `profiles.py`) is modified to call the same history-push helper before overwriting `resume_data.json`, so file-replace and section-edits share one timeline. To make this shareable without a circular import between the two route modules, the push/prune/restore logic lives as plain functions in a new `a2a/resume_history.py` (not tied to FastAPI or either router) — both `profiles.py` and `resume_versions.py` import from it.

**Errors:** unknown `version_id` → 404; `item_index` out of range → 400; a draft-generation failure (bad AI JSON) returns an error with nothing mutated — drafts never touch `resume_data.json` until `apply` is called.

## 4. AI drafting behaviour

Reuses the existing pattern from `parse_resume` — same `MODEL` from `core/config.py`, same `extract_json_object`/`extract_json_array` helpers. No new AI plumbing, just a narrower prompt per request.

- **Edit**: prompt includes the current item's JSON (or current scalar value) plus the user's instruction; Claude returns exactly one revised item/value, matching the same shape, replacing `item_index`.
- **Add**: prompt includes the instruction plus the section's schema/example only. One instruction can describe more than one addition ("add French and German," "learned Kafka and improved my Python skills"), so the draft returns a **list** of one or more new items. The editable preview shows all drafted items; the user can edit or remove any before confirming. `apply` appends whatever remains as one batch — still a single history version.
- **Delete**: no AI call — direct removal by `item_index` (or `{group, skill}` for Skills).

## 5. Frontend

**New page: `web/app/profile/[slug]/edit/page.tsx`**, linked from the existing read-only profile page (which becomes purely a viewer — no more inline editing affordances there).

- Same section layout/order as the read-only page.
- **List-based sections**: each existing item shows Edit / Delete icon buttons; each section has an **Add new** button.
  - Add new / Edit → instruction textarea → `POST .../draft` → the draft renders as an **editable form** matching the item's fields → hand-edit anything → **Confirm** (`POST .../apply`) or **Cancel** (discard, nothing saved).
  - Delete → confirm dialog only (no AI/draft step) → `POST .../apply` with `action: "delete"`.
  - Skills: Add new asks for a group (autocomplete against existing groups, or type a new one) plus the skill text.
- **Scalar fields**: single Edit affordance → instruction textarea → draft → editable text preview → Confirm/Cancel.
- **History panel** (tab or collapsible section on the same page): version list (timestamp + `change_summary`), each with **View** (read-only snapshot, reusing the existing structured display component) and **Restore** (confirm dialog → `POST .../restore`).
- **Replace Resume** (the existing `ReplaceResumeModal` full-file-upload flow) moves from the read-only profile page onto this `/edit` page, alongside the section tools, since it now shares the same version history.

## 6. Testing

Per project convention (TDD, mock only the genuine external boundary — the Anthropic API call):

- History helper: push/prune caps at 20, FIFO oldest-out; restore pushes current before overwriting
- Apply logic per section kind: add/edit/delete for list-of-objects, flat-list, grouped-list (Skills group auto-create / auto-remove-when-empty), scalar edit
- API tests per endpoint (`draft`, `apply`, `history` list/get, `restore`) with the Anthropic call mocked, in the style of the existing `tests/test_profiles_api.py`
- Regression: full-file replace (`resume/confirm`) still pushes a history snapshot correctly

## Out of scope

- Chat-style multi-turn refinement of a single draft (explicitly ruled out in favour of instruction → editable preview → confirm)
- Editing the raw uploaded PDF/DOCX file itself, or retaining original uploaded files in history (only parsed JSON snapshots are versioned)
- Diff/patch-based history storage
