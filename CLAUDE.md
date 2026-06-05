# Resume Builder — Project Context

## Stack

- **Backend**: Python 3.9, FastAPI, uvicorn, SQLite (stdlib sqlite3), Anthropic SDK, Playwright
- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, dnd-kit, lucide-react
- **AI**: Claude Sonnet for tailoring/parsing; Claude Haiku for search brief generation
- **PDF**: Playwright/Chromium renders the Jinja2 HTML template to PDF

## Commands

```bash
# Backend (port 8000)
python3 -m uvicorn a2a.server:app --port 8000

# Frontend (port 3000)
cd web && npm run dev

# Tests
python3 -m pytest tests/ -v

# Frontend typecheck
cd web && npm run typecheck
```

## File Structure

```
agents/            CLI agents: tailor_agent, job_search_agent, linkedin_agent, main_agent
a2a/
  server.py        FastAPI app — mounts all route modules
  routes/          REST endpoints: profiles, applications, tailor_api, search_brief
  skills/          A2A JSON-RPC skill wrappers
  db.py            SQLite CRUD helpers for applications tracker
core/
  config.py        Shared: MODEL, HUMANISE_RULES, extract_json_object/array
  resume_builder.py  render_resume(data, html_path, pdf_path) — PDF generator
  resume_template.html  Jinja2 template — single source of truth for PDF output
data/
  profiles/{slug}/
    resume_data.json   Profile resume data
    search_brief.json  Generated search signals
  applications.db    SQLite database (applications tracker)
output/
  profiles/{slug}/   Tailored PDFs, cover letters, JSON per profile
web/
  app/             Next.js pages (App Router)
  components/      React components
  lib/
    api.ts         Typed API client — all frontend → backend calls go here
    types.ts       Shared TypeScript interfaces
    useActiveProfile.ts  Hook for active profile state
docs/
  plans/           Implementation plans
  specs/           Design specs
tests/             pytest tests (unit + API)
```

## Architecture Decisions

**Shared constants in `core/config.py`**
MODEL, HUMANISE_RULES, and JSON extraction helpers live here. Never define MODEL in an individual agent file — it was hardcoded across three files and caused drift.

**Long AI calls run as background tasks**
The Next.js proxy times out at ~10s. Claude API calls for tailoring and search brief generation take 15–50s. Pattern: POST returns immediately with a job ID or `{"status":"generating"}`, frontend polls GET until ready. See `a2a/routes/tailor_api.py` and `a2a/routes/search_brief.py`.

**Profile data is files, not DB**
Resume data and search briefs live in `data/profiles/{slug}/` as JSON files. SQLite is only used for the applications tracker. Keeps profiles portable and human-readable.

**No subprocess in agents**
`tailor_agent.py` used to call `resume_builder.py` via `subprocess.run()`. It now imports and calls `render_resume()` directly. Subprocess was fragile and hard to debug.

**Search brief uses Haiku, not Sonnet**
Generation runs in a background task. Haiku is 4–5x faster and sufficient for structured signal extraction. Sonnet is reserved for tailoring and cover letters where quality matters more.

**Output always uses the Jinja2 template**
All resume PDFs — tailored or base — render through `core/resume_template.html`. There is no alternative template path.

## Python 3.9 Compatibility

This codebase runs on Python 3.9. Always use:
- `Optional[str]` not `str | None`
- `List[dict]` not `list[dict]`
- `Dict[str, str]` not `dict[str, str]`

## Constraints

- **Never** define `MODEL = "claude-..."` in individual agent files. Import from `core/config.py`.
- **Never** call `resume_builder.py` via subprocess. Use `render_resume()` directly.
- **Never** write directly to files in `data/` from the frontend — always go through API routes.
- **Never** commit `web/.next/`, `node_modules/`, or `data/applications.db`.
- **Never** use `allow_origins=["*"]` — CORS is scoped via the `CORS_ORIGINS` environment variable.
- **Never** add a new page without adding it to `web/components/TopNav.tsx`.

## Key Files

| File | Purpose |
|---|---|
| `core/config.py` | MODEL, HUMANISE_RULES, JSON helpers — single source of truth |
| `core/resume_builder.py` | `render_resume()` — PDF generation entry point |
| `agents/tailor_agent.py` | Resume tailoring, cover letter, humanise — main AI workhorse |
| `a2a/server.py` | FastAPI app — add new routers here |
| `a2a/routes/profiles.py` | Profile CRUD, resume parse/confirm |
| `a2a/routes/search_brief.py` | Search brief generate (background), get, patch signals |
| `a2a/db.py` | SQLite CRUD for applications tracker |
| `web/lib/api.ts` | All frontend API calls — add new endpoints here |
| `web/lib/types.ts` | Shared TypeScript types — add new interfaces here |
| `web/components/TopNav.tsx` | Navigation — add new pages here |

## User Context

Rohit Vishnu Mopuri — Data Integration Architect. Full profile and preferences at `~/.claude/projects/-Users-rohit-resume-builder/memory/`.
