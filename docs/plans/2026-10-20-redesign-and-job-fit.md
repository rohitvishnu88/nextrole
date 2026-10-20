# Bauhaus-lite Redesign + Job Fit Features: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin the whole web app in the approved Bauhaus-lite style and rebuild the dashboard. Then add job analysis, a weighted match score, truthful tailoring (change log and fabrication check), an ATS view and follow-ups.

**Architecture:** Part A replaces the Tailwind theme with semantic tokens and restyles every page, deleting the old tokens so that leftovers are visible. Part B adds three pure, deterministic Python modules in `core/` (score, fabrication, ATS) and one agent module for the Claude analysis with an on-disk cache. It wires them into the existing tailor and job-search background-task flows, and adds UI sections built from Part A's primitives.

**Tech Stack:** Python 3.9, FastAPI, SQLite, Anthropic SDK, pdfplumber, Playwright; Next.js 14, Tailwind, lucide-react, Jost via `next/font/google`.

**Specs:**
- `docs/specs/2026-10-20-bauhaus-redesign-design.md` (Part A)
- `docs/specs/2026-10-20-job-fit-features-design.md` (Part B)

## Global Constraints

- Python 3.9 typing only: `Optional[str]`, `List[dict]`, `Dict[str, str]`. No `X | None`, no bare `list[...]` in new code.
- `MODEL` is imported from `core/config.py`. Never define a model string in a module. Parse model JSON with `extract_json_object` / `extract_json_array`.
- Long Claude calls run as background tasks with polling, and no request blocks for more than about 10s.
- All frontend → backend calls go in `web/lib/api.ts`, and all shared types in `web/lib/types.ts`.
- Every slug or ID that ends up in a path is validated. Use `resume_history.validate_slug` for profiles, and an anchored regex for IDs.
- The resume PDF template `core/resume_template.html` is **not** touched.
- Colour tokens: `paper #F5F4F0`, `surface #FFFFFF`, `ink #000000`, `ink-muted #5A5A57`, `rule #000000`, `rule-soft #D9D7D0`, `blue #378ADD`, `yellow #EF9F27`, `red #E24B4A`.
- Yellow is never used as a text colour, only as a fill. No `rounded-*` except the page circle (`rounded-full`) and status squares (none). No `shadow-*`, no gradients.
- Static UI strings in headings, navigation and buttons are lowercase in the source. User content (names, titles, companies, resume text) keeps its own casing. No global CSS `lowercase`.
- Match score: weights high 3, medium 2, low 1, filler 0; credit yes 1, partly 0.5, no 0; `round(100 × Σ(w×c) / Σw)`; bands ≥70 blue, 45–69 yellow, <45 red.
- Follow-up default: applied date + 7 days. "Followed up" sets today + 7 days.
- `fetch_job_description` text cap: 20,000 characters (was 4,000).
- Tests: `python3 -m pytest tests/<file>.py -v` for each task. **Never** run bare `pytest tests/`: `tests/test_tailor.py` is a script that makes a live tailoring call when it's imported. The final full run uses `--ignore=tests/test_tailor.py`. Mock only the Anthropic client and Tavily/HTTP fetches.
- Frontend checks: `cd web && npm run typecheck` must exit 0.

## Review Focus

1. **The fetched job ad is empty or tiny** (login wall, Workday JS shell). The analysis must fail with a clear message ("couldn't read the full job ad") and never produce a verdict from a few lines. Pinned in Task B5.
2. **The model returns partial or odd JSON** (missing `meets`, unknown `filter_likelihood`, non-list `requirements`). Normalise it: an unknown likelihood counts as `low` and an unknown `meets` as `no`, with no crash and no `NaN` score. Pinned in Tasks B1 and B5.
3. **An existing `applications.db` from before this change.** The migration is idempotent and keeps the old rows. Pinned in Task B4.
4. **Clicking analyse twice on the same job, or analysing while a search runs.** The second request returns the current status and doesn't start a second Claude call. Pinned in Task B6.
5. **A hand-edited tailored resume with missing sections** (no `skills`, empty `experience`). The fabrication check and the ATS re-run don't crash. Pinned in Tasks B2 and B8.

---

# Part A: Redesign

### Task A1: Theme tokens, font, base layout

**Files:**
- Modify: `web/tailwind.config.ts`, `web/app/globals.css`, `web/app/layout.tsx`

**Interfaces:**
- Produces: Tailwind colours `paper surface ink ink-muted rule rule-soft blue yellow red`. `font-sans` is Jost (CSS var `--font-jost`). The old tokens `cream accent accent-hover accent-light navy warm-border muted green-soft green-text` and `font-brand` are **removed**, and the `borderRadius` overrides are removed.

- [ ] **Step 1:** In `tailwind.config.ts`, replace `colors` with the token table from Global Constraints. Delete the `borderRadius` and `brand` font entries. Set `fontFamily.sans: ["var(--font-jost)", "system-ui", "sans-serif"]`.
- [ ] **Step 2:** In `layout.tsx`, swap Inter and Space_Grotesk for `Jost({ subsets: ["latin"], variable: "--font-jost", weight: ["400","500","700"], display: "swap" })`. Change the body class to `bg-paper text-ink`.
- [ ] **Step 3:** In `globals.css`, set the body background `#F5F4F0`, colour `#000`, and the Jost font variable. Drop the Inter `font-feature-settings`. Make the scrollbar thumb `#000` with no radius.
- [ ] **Step 4:** Run `cd web && npm run typecheck`. Expected: exit 0.
- [ ] **Step 5:** Commit: `feat(web): replace warm theme with Bauhaus-lite tokens and Jost`.

### Task A2: Shared primitives and chrome

**Files:**
- Create: `web/components/ui/StatusMarker.tsx`, `web/components/ui/PageCircle.tsx`, `web/components/ui/ScoreMarker.tsx`
- Delete: `web/components/StatusBadge.tsx` (update all importers)
- Modify: `TopNav.tsx`, `Footer.tsx`, `Sidebar.tsx`, `ProfileSwitcher.tsx`, `ConfirmDialog.tsx`, `AddProfileModal.tsx`, `ReplaceResumeModal.tsx`, `AddApplicationModal.tsx`

**Interfaces:**
- Produces:
  - `StatusMarker({ status }: { status: ApplicationStatus })`: a 10px square followed by a lowercase label. saved → `bg-ink`, applied → `bg-yellow`, interview → `bg-blue`, offer → `bg-blue` with a bold label, rejected → `bg-red`.
  - `PageCircle({ colour = "blue" }: { colour?: "blue" | "yellow" | "red" })`: an absolutely positioned flat circle, about 340px, bleeding off the top-right, with `aria-hidden` and `pointer-events-none`. The parent must be `relative overflow-hidden`.
  - `ScoreMarker({ score }: { score: number | null })`: a bold number plus a 10px square, coloured by `scoreBand(score)` (≥70 blue, 45–69 yellow, <45 red). Renders "—" for null. Export `scoreBand(score: number): "blue" | "yellow" | "red"` from the same file.
- Button convention, used by every later task: primary is `bg-ink text-paper px-4 py-2`, secondary is `border-[1.5px] border-ink px-4 py-2`, destructive is `bg-red text-paper`. No radius.
- Modal convention: overlay `bg-ink/50`, panel `bg-surface border-[1.5px] border-ink`, no radius, no shadow.

- [ ] **Step 1:** Create the three primitives with the exact props above.
- [ ] **Step 2:** Replace every `StatusBadge` import with `StatusMarker`, then delete `StatusBadge.tsx`.
- [ ] **Step 3:** Restyle the chrome and modal files listed above. Nav items are lowercase, the brand reads `nextrole.` in Jost 700, and there's a 1.5px `border-ink` rule under the nav.
- [ ] **Step 4:** Typecheck, which must exit 0. Then run `grep -rnE 'rounded-|shadow-' web/components/{TopNav,Footer,Sidebar,ProfileSwitcher,ConfirmDialog,AddProfileModal,ReplaceResumeModal,AddApplicationModal}.tsx`. Expected: no matches.
- [ ] **Step 5:** Commit: `feat(web): add status/score/circle primitives and restyle app chrome`.

### Task A3: Working screens (applications, jobs, tailor)

**Files:**
- Modify: `web/app/applications/page.tsx`, `web/components/ApplicationTable.tsx`, `web/components/ApplicationKanban.tsx`, `web/app/jobs/page.tsx`, `web/components/JobCard.tsx`, `web/app/tailor/page.tsx`, `web/app/tailor/[job_id]/edit/page.tsx`

**Interfaces:**
- Consumes: the A2 primitives and button convention.

- [ ] **Step 1:** Restyle the files above. Tables use full-width rules between rows (`border-t border-rule-soft`) and a `border-t-[1.5px] border-ink` header. Kanban columns have no tint, just a header rule. Job-source badges become ink text. Success ticks and completed states use `text-blue`. No `PageCircle` on these screens.
- [ ] **Step 2:** Typecheck, which must exit 0. Then run the old-token grep (Task A5, Step 2) on these files. Expected: no matches.
- [ ] **Step 3:** Commit: `feat(web): restyle applications, jobs and tailor screens`.

### Task A4: Profile, search brief, about

**Files:**
- Modify: `web/app/profile/[slug]/page.tsx`, `web/app/profile/[slug]/edit/page.tsx`, `web/components/resume-edit/*.tsx`, `web/app/search-brief/page.tsx`, `web/components/SignalChip.tsx`, `web/components/QueryPreview.tsx`, `web/app/about/page.tsx`

- [ ] **Step 1:** Restyle the files above. Code blocks (`bg-gray-950`) become `bg-ink text-paper`. Non-status dots on About become ink. `PageCircle` goes on `/about` (yellow) and `/search-brief` (red), behind the title. None on the profile edit page.
- [ ] **Step 2:** Typecheck, which must exit 0. Then run the old-token grep on these files. Expected: no matches.
- [ ] **Step 3:** Commit: `feat(web): restyle profile, search brief and about pages`.

### Task A5: Dashboard rebuild and sweep

**Files:**
- Modify: `web/app/page.tsx`
- Create: `web/lib/greeting.ts`

**Interfaces:**
- Produces: `greeting(now: Date): "good morning" | "good afternoon" | "good evening"`, with boundaries at 12:00 and 18:00 local time.
- Consumes: `api.listApplications`, `api.getTailorHistory`, `api.listProfiles` (for the profile name), and the A2 primitives.

- [ ] **Step 1:** Rebuild the dashboard in the spec's order. First the title `{greeting(new Date())}, {profile.name}` with `PageCircle` in blue. Then a summary line, which shows the active-application count for now; Task B13 changes it. Then the primary "tailor a resume" link to `/tailor`. Then the stat blocks (applications, interviews, offers) with a `border-l-[3px] border-ink` and the number at 36px/700. Then recent applications: the top 5 by `updated_at`, with role and company, date and `StatusMarker`, plus a "view all" link to `/applications`. Last, the existing tailored-resumes list with rules. Remove the hero card.
- [ ] **Step 2:** Run the old-token sweep, which is the acceptance check for all of Part A:
  `grep -rnE '\b(cream|navy|warm-border|accent|muted|green-soft|green-text|font-brand)\b|bg-gray-|text-gray-|border-gray-|rounded-(sm|md|lg|xl|2xl|3xl)|\brounded\b|shadow' web/app web/components | grep -v 'ink-muted'`
  Expected: no output. `rounded-full` is allowed only in `PageCircle.tsx`.
- [ ] **Step 3:** Typecheck, which must exit 0.
- [ ] **Step 4:** Visual check in the running app (`./start.sh`, then the browser pane). Check every page against `.superpowers/brainstorm/*/content/visual-direction.html` option C, at desktop width and at 375px.
- [ ] **Step 5:** Commit: `feat(web): rebuild dashboard with greeting, stats and recent applications`.

---

# Part B: Job fit features

Test helper used by every task that mocks Claude, defined once in `tests/fakes.py` (created in Task B5):

```python
class FakeClient:
    """Stands in for anthropic.Anthropic. Returns queued texts in order and records prompts."""
    def __init__(self, *texts: str): ...
    # .messages.create(**kwargs) -> object with .content[0].text; appends kwargs to .calls
```

### Task B1: Match score (`core/job_score.py`)

**Files:**
- Create: `core/job_score.py`, `tests/test_job_score.py`

**Interfaces:**
- Produces:
  - `WEIGHTS = {"high": 3, "medium": 2, "low": 1, "filler": 0}`, `CREDIT = {"yes": 1.0, "partly": 0.5, "no": 0.0}`
  - `compute_match_score(requirements: List[dict]) -> Optional[int]`. Each dict has `filter_likelihood` and `meets`. An unknown likelihood counts as `"low"`, and an unknown or missing `meets` as `"no"`. Returns `None` when Σweight is 0.
  - `score_band(score: int) -> str`, which returns `"blue"`, `"yellow"` or `"red"`.

- [ ] **Step 1: Write the failing tests:**
  - `test_weighted_score`: `[{high,yes},{medium,partly},{low,no},{filler,no}]` gives `round(100*(3+1)/6)` = `67`
  - `test_all_filler_returns_none`, which returns `None`
  - `test_unknown_values_are_normalised`: `[{"filter_likelihood":"critical","meets":None}]` gives `0` (counts as low/no)
  - `test_score_band_edges`: 70 → blue, 69 → yellow, 45 → yellow, 44 → red
- [ ] **Step 2:** Run `python3 -m pytest tests/test_job_score.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3:** Implement `compute_match_score` and `score_band` in `core/job_score.py`.
- [ ] **Step 4:** Run the same command. Expected: 4 passed.
- [ ] **Step 5:** Commit: `feat: add weighted match score from job analysis`.

### Task B2: Fabrication check (`core/fabrication.py`)

**Files:**
- Create: `core/fabrication.py`, `tests/test_fabrication.py`

**Interfaces:**
- Produces: `find_fabrications(base: dict, tailored: dict) -> List[dict]`. Each flag is `{"location": str, "kind": "number" | "skill" | "name" | "identity", "text": str}`. `location` uses the same keys as the change log: `"summary"`, `"skills"`, `"experience[i].description[j]"` and `"experience[i]"` for identity fields.
- Rules:
  - The comparison corpus is all the string values in `base`, joined and lowercased.
  - **number:** matches of `[£$€]?\d[\d,.]*\s?(%|k|m|bn|x|\+)?`, normalised by stripping spaces, that are absent from the corpus.
  - **skill:** every skill string in `tailored["skills"]` (any group shape the resume uses) absent from the corpus.
  - **name:** tokens in the summary and bullets that match `[A-Za-z][A-Za-z0-9+#./-]*`, contain an uppercase letter that isn't word-initial or a digit, or are all-caps with 2+ letters, and are absent from the corpus. Plain sentence-initial capitalised words are ignored.
  - **identity:** any difference in `title`, `company`, `start_date` or `end_date` per experience index, or in `name`, `email` or `phone`.
  - Missing keys mean empty. Never raise on a missing section.

- [ ] **Step 1: Write the failing tests:**
  - `test_new_metric_flagged`: base bullet "Cut costs", tailored "Cut costs by 40%" gives one flag `{"kind":"number","text":"40%","location":"experience[0].description[0]"}`
  - `test_reworded_bullet_not_flagged`: same facts, different words, gives `[]`
  - `test_new_skill_flagged`: tailored skills include "Terraform", which is absent from base, so it's flagged with `kind "skill"`
  - `test_new_tech_name_flagged`: "Migrated to PySpark" where base has no "pyspark" gives `kind "name"`, text `"PySpark"`
  - `test_title_change_flagged_as_identity`
  - `test_missing_sections_do_not_crash`: `find_fabrications({"name":"A"}, {"name":"A","experience":[]})` gives `[]`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_fabrication.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `find_fabrications` per the rules above. Read `data/profiles/rohit/resume_data.json` to see the real shape of `skills`.
- [ ] **Step 4:** Run the same command. Expected: 6 passed.
- [ ] **Step 5:** Commit: `feat: add deterministic fabrication check for tailored resumes`.

### Task B3: ATS check (`core/ats_check.py`)

**Files:**
- Create: `core/ats_check.py`, `tests/test_ats_check.py`

**Interfaces:**
- Produces:
  - `extract_pdf_text(pdf_path: str) -> str`, which joins the pdfplumber `page.extract_text()` output in page order.
  - `check_ats(text: str, terms: List[str]) -> dict`, which returns `{"contact": {"email": bool, "phone": bool}, "headings": {"summary": bool, "experience": bool, "skills": bool, "education": bool}, "terms": [{"term": str, "present": bool}], "text": str}`. Matching is case-insensitive and whitespace-collapsed. `terms` are deduplicated case-insensitively, in their original order.

- [ ] **Step 1: Write the failing tests:**
  - `test_check_ats_terms_and_headings`: given text with "EXPERIENCE", "Skills", an email and "+44 7700 900123", and terms `["Kafka","event-driven architecture","Kafka"]`, the result is email and phone True, experience and skills True, summary False, and terms `[Kafka present, event-driven architecture missing]` (deduplicated)
  - `test_extract_pdf_text_from_real_render`: renders `{"name":"Test User","summary":"Kafka specialist","experience":[]}` with `core.resume_builder.render_resume` into `tmp_path`, then asserts that "Kafka" is in `extract_pdf_text(pdf)`. This uses real Playwright and must not be mocked.
- [ ] **Step 2:** Run `python3 -m pytest tests/test_ats_check.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement both functions.
- [ ] **Step 4:** Run the same command. Expected: 2 passed.
- [ ] **Step 5:** Commit: `feat: add ATS text extraction and term check`.

### Task B4: Applications migration and follow-ups

**Files:**
- Modify: `a2a/db.py`, `a2a/routes/applications.py`, `tests/test_applications_api.py`

**Interfaces:**
- Produces:
  - Columns `follow_up_date TEXT`, `match_score INTEGER` and `analysis_id TEXT`. `init_db()` adds them with `ALTER TABLE applications ADD COLUMN` only when `PRAGMA table_info` shows them missing.
  - `apply_status_rules(fields: dict, current: Optional[dict], today: date) -> dict`. When the resulting status is `applied`: if `applied_date` is empty, set it to `today.isoformat()`. If `follow_up_date` is empty and wasn't explicitly provided, set it to applied date + 7 days. Used by both create and update.
  - `db.update_application` allows `follow_up_date`, `match_score` and `analysis_id`, and accepts `None` values (clear).
  - `ApplicationCreate` gains `follow_up_date`, `match_score` and `analysis_id` (all Optional).
  - `PATCH /api/applications/{id}` builds `fields` from `body.model_fields_set`, so an explicit `null` clears the field and an omitted one is untouched.
  - `POST /api/applications/{id}/followed-up` sets `follow_up_date` to today + 7 days and returns `{"follow_up_date": "YYYY-MM-DD"}`, or 404 if the application doesn't exist.
  - Each row returned by `GET /api/applications` gains `"overdue": bool`, which is True when status is `applied` or `interview`, `follow_up_date` is set, and `follow_up_date <= today`.

- [ ] **Step 1: Write the failing tests** (the `today` argument is injectable, so tests can fix the date):
  - `test_migration_adds_columns_to_old_db`: create a DB file with the **old** CREATE TABLE and one row, then call `init_db()` twice. The columns exist and the row is intact.
  - `test_create_applied_sets_dates`: create with `status="applied"` and no dates, so `applied_date` is today and `follow_up_date` is today + 7
  - `test_patch_to_applied_keeps_existing_applied_date`
  - `test_patch_explicit_null_clears_follow_up`: PATCH `{"follow_up_date": null}` sets it to None, and PATCH `{}` leaves other fields alone
  - `test_followed_up_endpoint_moves_date`
  - `test_overdue_flag`: applied with follow-up yesterday is True, rejected with follow-up yesterday is False
- [ ] **Step 2:** Run `python3 -m pytest tests/test_applications_api.py -v`. Expected: the new tests fail.
- [ ] **Step 3:** Implement the interfaces above.
- [ ] **Step 4:** Run the same command. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add follow-up dates and score columns to applications`.

### Task B5: Job analysis agent and cache (`agents/job_analysis.py`)

**Files:**
- Create: `agents/job_analysis.py`, `tests/fakes.py`, `tests/test_job_analysis.py`
- Modify: `agents/tailor_agent.py` (raise both `[:4000]` caps in `fetch_job_description` to `[:20000]`)

**Interfaces:**
- Consumes: `compute_match_score` (B1), `MODEL`, `extract_json_object`.
- Produces:
  - `MIN_JD_CHARS = 400`
  - `class JobTextTooShort(Exception)`, raised by `analyse_job` when the normalised text has fewer than `MIN_JD_CHARS` characters. The message is "Couldn't read the full job ad. Paste the job description text instead."
  - `make_analysis_id(jd_text: str, resume: dict) -> str`: `sha256(normalise(jd_text) + "\n" + sha256(json.dumps(resume, sort_keys=True)))`, first 16 hex characters. `normalise` lowercases and collapses whitespace.
  - `ANALYSIS_ID_RE = re.compile(r"^[a-f0-9]{16}$")`
  - `analyse_job(client, resume: dict, jd_text: str) -> dict`. One Claude call whose prompt includes Rohit's prompts 1 and 2 **word for word** from the spec appendix, plus the JSON schema from the spec's "Analysis contents" section (including `key_terms` per requirement). The result is normalised with `normalise_analysis`, then gets `match_score = compute_match_score(requirements)`, `analysis_id`, and `created_at`.
  - `normalise_analysis(raw: dict) -> dict` guarantees every field exists with the right type. `requirements` becomes a list. Unknown enum values go to `low` or `no`. `gaps_that_matter` is truncated to 3.
  - `analysis_path(profile_slug: str, analysis_id: str) -> Path`, which returns `ROOT/output/profiles/{slug}/analyses/{id}.json` and validates both the slug and `ANALYSIS_ID_RE`.
  - `load_analysis(profile_slug, analysis_id) -> Optional[dict]`, `save_analysis(profile_slug, analysis: dict) -> None`
  - `get_or_create_analysis(client, profile_slug: str, resume: dict, jd_text: str) -> dict` returns the cached result if present, and otherwise analyses and saves it.

- [ ] **Step 1: Write `tests/fakes.py`** (FakeClient, as above) **and the failing tests:**
  - `test_analysis_id_stable_and_resume_sensitive`: same text with different whitespace gives the same ID, and a changed resume gives a different ID
  - `test_analyse_job_uses_verbatim_prompts_and_scores`: FakeClient returns a JSON analysis with 2 requirements, `{high,yes}` and `{low,no}`. The prompt in `client.calls[0]` contains "Rank the requirements by how likely each is to be a real filter." and "Be blunt.", and the result has `match_score == 75`
  - `test_short_text_raises`: 50 characters raise `JobTextTooShort`, and no Claude call is made
  - `test_malformed_model_output_normalised`: the model returns `{"requirements": "oops"}`, so the result has `requirements == []`, `match_score is None`, and every top-level field present
  - `test_get_or_create_caches`: two calls with a monkeypatched `ROOT` to `tmp_path` make exactly one Claude call
  - `test_analysis_path_rejects_bad_id`: `"../../x"` raises ValueError
- [ ] **Step 2:** Run `python3 -m pytest tests/test_job_analysis.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the interfaces above and raise the fetch caps.
- [ ] **Step 4:** Run the same command. Expected: 6 passed.
- [ ] **Step 5:** Commit: `feat: add job analysis agent with verbatim decode/score prompts and cache`.

### Task B6: Analyse-a-job API (tier 2 from the Jobs page)

**Files:**
- Create: `a2a/routes/job_analysis.py`, `tests/test_job_analysis_api.py`
- Modify: `a2a/server.py` (include the router), `agents/job_store.py` (`set_analysis(store, job_id, analysis_id) -> bool`)

**Interfaces:**
- Consumes: B5 `get_or_create_analysis`, `load_analysis`, `JobTextTooShort`; `tailor_agent.fetch_job_description`; `job_store.load_store`/`save_store`.
- Produces:
  - `POST /api/profiles/{slug}/job-search/{job_id}/analyse`: 404 if the job is unknown. If an analysis for this job is already running, it returns `{"status":"analysing"}` without starting a second one, using an in-process `_running` set keyed by `(slug, job_id)` behind a lock, as in `job_search.py`. Otherwise it starts a `BackgroundTasks` task and returns `{"status":"analysing"}`.
  - `GET /api/profiles/{slug}/job-search/{job_id}/analysis` returns one of `{"status":"analysing"}`, `{"status":"none"}`, `{"status":"failed","error":str}` or `{"status":"ready","analysis":{...}}`.
  - The background task fetches the job text, runs `get_or_create_analysis`, records the ID with `job_store.set_analysis`, and stores errors in `_last_error[(slug, job_id)]`.
  - `job_store` entries gain `analysis_id` (optional). `visible_jobs` output is otherwise unchanged.

- [ ] **Step 1: Write the failing tests** (monkeypatch `fetch_job_description`, the client factory and `ROOT`):
  - `test_analyse_then_ready`
  - `test_second_analyse_while_running_does_not_start_again`: pre-seed `_running`, POST, and assert the fake analysis function was never called
  - `test_short_text_reports_failed_with_message`
  - `test_unknown_job_404` and `test_bad_slug_400`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_job_analysis_api.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the endpoints, `set_analysis` and the router registration.
- [ ] **Step 4:** Run the same command. Expected: pass.
- [ ] **Step 5:** Commit: `feat: add on-demand job analysis endpoints for the Jobs page`.

### Task B7: Triage on search results (tier 1)

**Files:**
- Modify: `agents/job_search_agent.py`, `agents/job_store.py`, `tests/test_job_store.py`

**Interfaces:**
- Produces:
  - The scoring prompt's output schema gains `"red_flags": ["..."]`, described in the prompt as "explicit blockers stated in the text only, e.g. no visa sponsorship, security clearance required, on-site in a non-UK location. Empty list if none." No other prompt change.
  - In `run()`, collect the URLs passed to `read_job_page` into `read_urls`. Before `process_search_results`, set each raw job's `text_basis` to `"full"` if its URL is in `read_urls`, and `"snippet"` otherwise. This is computed in Python, not by the model.
  - `merge_job` copies `red_flags` (list, default `[]`) and `text_basis` (default `"snippet"`) on insert, and refreshes them on update for new or seen jobs.

- [ ] **Step 1: Write the failing tests** in `test_job_store.py`: `test_merge_job_stores_triage_fields`, and `test_merge_job_defaults_triage_fields` for a candidate without the fields.
- [ ] **Step 2:** Run `python3 -m pytest tests/test_job_store.py -v`. Expected: the new tests fail.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run the same command, plus `python3 -m pytest tests/test_job_search_api.py -v`. Expected: pass.
- [ ] **Step 5:** Commit: `feat: add red flags and text basis triage to job search results`.

### Task B8: Truthful tailoring pipeline

**Files:**
- Modify: `agents/tailor_agent.py`
- Create: `tests/test_tailor_fit.py`

**Interfaces:**
- Consumes: B5 `get_or_create_analysis`, B2 `find_fabrications`, B3 `extract_pdf_text` and `check_ats`.
- Produces:
  - `tailor_resume(client, resume: dict, jd_text: str, analysis: Optional[dict] = None) -> dict`, which now returns `{"resume": {...}, "changes": [...]}`. The prompt contains prompt 3's may and may-not lists **word for word**, keeps the existing "Do not change: name, email, …" line and `HUMANISE_RULES`, and, when an analysis is passed, lists its high and medium requirement texts and `search_terms` as targets. Each change is `{"location","kind","before","after","needs_confirmation","reason"}`, with `location` keys as in B2.
  - `realign_changes(changes: List[dict], final_resume: dict) -> List[dict]` replaces each change's `after` with the text at `location` in `final_resume`. For a location that doesn't resolve, it keeps the original `after` and adds `"stale": True`.
  - `ats_terms(analysis: Optional[dict]) -> List[str]`: `search_terms` plus `key_terms` of high-likelihood requirements.
  - `run(...)` order: get the JD, then `analysis = get_or_create_analysis(...)`. On `JobTextTooShort`, set `analysis = None` and still tailor; tailoring isn't blocked. Then tailor, humanise as today, `realign_changes`, cover letter, save the JSON, render the PDF, then `flags = find_fabrications(base, tailored)` and `ats = check_ats(extract_pdf_text(pdf), ats_terms(analysis))`.
  - New sidecars: `base_{url_slug}.json` (a copy of the base resume used) and `fit_{url_slug}.json` = `{"analysis_id": Optional[str], "changes": [...], "fabrication_flags": [...], "ats": {...}}`. `meta_{url_slug}.json` gains `analysis_id`.
  - `run()` return dict gains `"fit_file"`, `"base_file"` and `"analysis_id"`.
  - `recheck_fit(json_file: str, pdf_file: str, base_file: str, fit_file: str) -> dict` recomputes `fabrication_flags` and `ats` from the files on disk, rewrites `fit_file`, and returns the new fit dict (with the changes left unchanged). Used by B9.

- [ ] **Step 1: Write the failing tests:**
  - `test_realign_changes_uses_final_wording`: a change at `experience[0].description[1]` gets `after` from the final resume
  - `test_realign_marks_unresolvable_location_stale`
  - `test_tailor_prompt_contains_rules_verbatim`: FakeClient, then assert the prompt contains "You may not:" and "stuff in keywords, or list a skill I could not be tested on"
  - `test_ats_terms_from_analysis`: only high requirements' `key_terms`, plus `search_terms`, deduplicated by B3
  - `test_recheck_fit_flags_hand_added_metric`: write the base/tailored/fit files into `tmp_path`. The tailored file has a bullet with "by 30%", and `extract_pdf_text` is monkeypatched to return its text. `recheck_fit` returns a number flag, and the file on disk is updated.
  - `test_recheck_fit_survives_missing_sections`: the tailored JSON has no `skills` and no `experience`, and there's no crash
- [ ] **Step 2:** Run `python3 -m pytest tests/test_tailor_fit.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the interfaces above.
- [ ] **Step 4:** Run the same command, plus `python3 -m pytest tests/test_tailor_edit_api.py tests/test_tailor_history_api.py -v`. Expected: pass. Update fixtures only where the return shape of `tailor_resume` changed.
- [ ] **Step 5:** Commit: `feat: tailor under explicit truthfulness rules with change log, fabrication flags and ATS check`.

### Task B9: Tailor API: fit endpoint, re-check on edit, history score

**Files:**
- Modify: `a2a/routes/tailor_api.py`, `tests/test_tailor_edit_api.py`, `tests/test_tailor_history_api.py`

**Interfaces:**
- Consumes: B8 `run()` return keys, `recheck_fit`; B5 `load_analysis`.
- Produces:
  - The job dict stores `fit_file`, `base_file` and `analysis_id`.
  - `GET /api/tailor/{job_id}/fit` returns `{"analysis": Optional[dict], "changes": [...], "fabrication_flags": [...], "ats": {...}}`, or 404 if the job isn't completed.
  - `PATCH /api/tailor/{job_id}/data` re-renders as today, then calls `recheck_fit`, and returns `{"ok": True, "fit": {...}}`.
  - Each `GET /api/tailor/history/{slug}` entry gains `"match_score": Optional[int]` and `"verdict": Optional[str]`, read via `meta_{id}.json` → `analysis_id` → `load_analysis`. Both are null when missing.

- [ ] **Step 1: Write the failing tests:** `test_fit_endpoint_returns_sidecar`, `test_patch_data_rechecks_fit` (asserts the response `fit.fabrication_flags` includes a newly added metric), and `test_history_includes_score_and_verdict`, plus `test_history_score_null_without_analysis`.
- [ ] **Step 2:** Run `python3 -m pytest tests/test_tailor_edit_api.py tests/test_tailor_history_api.py -v`. Expected: the new tests fail.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run the same command. Expected: pass.
- [ ] **Step 5:** Commit: `feat: expose tailor fit results, re-check on edit, scores in history`.

### Task B10: Frontend types and API client

**Files:**
- Modify: `web/lib/types.ts`, `web/lib/api.ts`

**Interfaces:**
- Produces types that mirror the backend exactly: `Requirement`, `JobAnalysis`, `ChangeEntry`, `FabricationFlag`, `AtsResult`, `TailorFit`, and `JobAnalysisStatus` (a union of the four GET shapes). Also `Application` + `follow_up_date | match_score | analysis_id | overdue`, `JobMatch` + `red_flags: string[]; text_basis: "full" | "snippet"; analysis_id?: string`, and `TailorHistoryEntry` + `match_score: number | null; verdict: string | null`.
- Produces functions: `analyseJob(slug, jobId)`, `getJobAnalysis(slug, jobId)`, `getTailorFit(jobId)`, `markFollowedUp(appId)`. `updateApplication` accepts `follow_up_date: string | null`. `patchTailorData` returns `{ ok: boolean; fit: TailorFit }`.

- [ ] **Step 1:** Add the types and functions.
- [ ] **Step 2:** Typecheck, which must exit 0.
- [ ] **Step 3:** Commit: `feat(web): add types and API client for job fit features`.

### Task B11: Tailor result fit sections

**Files:**
- Create: `web/components/fit/VerdictSection.tsx`, `RequirementsTable.tsx`, `ChangesList.tsx`, `AtsView.tsx`, `AboutJob.tsx`
- Modify: `web/app/tailor/page.tsx`, `web/app/tailor/[job_id]/edit/page.tsx`

**Interfaces:**
- Consumes: B10 `getTailorFit` and types; A2 `ScoreMarker`, `StatusMarker` conventions.
- Produces: `VerdictSection({ analysis })`, `RequirementsTable({ requirements })` and `AboutJob({ analysis })` take a `JobAnalysis` and are reused by B12. `ChangesList({ changes, flags })` and `AtsView({ ats })`.

- [ ] **Step 1:** On a completed job, `/tailor` calls `getTailorFit` and renders, in the spec's order: Verdict (`ScoreMarker`, verdict and reason, 3 gaps, collapsible gaps that don't matter), Requirements, Changes (needs-confirmation rows and all fabrication flags first, each with a red square), Left off, ATS view (checks, present/missing terms, extracted text in `font-mono bg-surface`), and About this job. If `analysis` is null, show a single line: "job analysis unavailable — the full ad couldn't be read." Changes and ATS still render.
- [ ] **Step 2:** The edit page uses the `fit` returned by `patchTailorData` to show the updated flag count after saving.
- [ ] **Step 3:** Typecheck, which must exit 0. Then do a visual check: tailor one real job in the running app, and confirm every section renders and a red flag shows for an edit that adds "by 30%".
- [ ] **Step 4:** Commit: `feat(web): show verdict, requirements, changes and ATS view on tailor results`.

### Task B12: Jobs page triage and analyse

**Files:**
- Modify: `web/components/JobCard.tsx`, `web/app/jobs/page.tsx`

**Interfaces:**
- Consumes: B10 `analyseJob`, `getJobAnalysis`; B11 `VerdictSection`, `RequirementsTable`, `AboutJob`.

- [ ] **Step 1:** Each card shows `red_flags` as red-square lines, a `full ad` / `snippet` label, and a secondary "analyse" button. On click, call `analyseJob`, then poll `getJobAnalysis` every 3s until the status is `ready` or `failed`. While waiting, show "analysing…". When ready, show `ScoreMarker` and the verdict on the card, with an expandable panel holding the three reused sections. When failed, show the error text in a red-tinted line. On mount, cards whose job has `analysis_id` fetch their analysis straight away.
- [ ] **Step 2:** Typecheck, which must exit 0. Then do a visual check with one real search.
- [ ] **Step 3:** Commit: `feat(web): add triage flags and on-demand analysis to job cards`.

### Task B13: Follow-ups and scores in tracker and dashboard

**Files:**
- Modify: `web/components/ApplicationTable.tsx`, `web/components/ApplicationKanban.tsx`, `web/components/AddApplicationModal.tsx`, `web/app/tailor/page.tsx` (passes `match_score` and `analysis_id` into the modal), `web/app/page.tsx`

- [ ] **Step 1:** Table: add match (`ScoreMarker`) and follow-up columns. The follow-up column shows the date, red with "overdue" when `overdue`, a "followed up" button (`markFollowedUp`), and "clear" (`updateApplication(id, { follow_up_date: null })`). Kanban: cards show a red square when `overdue`. The modal sends `match_score` and `analysis_id` when opened from the tailor result.
- [ ] **Step 2:** Dashboard: the summary line becomes "{n} application(s) need a follow-up" when any are overdue, and falls back to the active count otherwise. Show the average-match stat block only when at least one application has a `match_score`, as the mean of those, rounded. Recent-application rows show `ScoreMarker` when the score is present. Tailored-resume rows show the score and verdict from history.
- [ ] **Step 3:** Typecheck, which must exit 0. Then do a visual check: create an application as applied, set its follow-up to yesterday via the API, and confirm the red markers on the dashboard, table and Kanban.
- [ ] **Step 4:** Commit: `feat(web): surface follow-ups and match scores in tracker and dashboard`.

### Task B14: Final verification

- [ ] **Step 1:** Run `python3 -m pytest tests/ -v --ignore=tests/test_tailor.py`. Expected: all pass.
- [ ] **Step 2:** Run `cd web && npm run typecheck`. Expected: exit 0.
- [ ] **Step 3:** Re-run the Part A old-token sweep (Task A5, Step 2). Expected: no output.
- [ ] **Step 4:** Walk through the full flow in the running app: run a search, analyse one job, tailor it, review the fit sections, edit a bullet to add a metric and save (the flag appears), add it to the tracker, and check the follow-up and score on the dashboard.
