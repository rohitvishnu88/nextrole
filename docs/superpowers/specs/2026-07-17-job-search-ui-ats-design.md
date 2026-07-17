# Job Search UI + Multi-Source ATS Search — Design

## Problem

The job search agent (`agents/job_search_agent.py`) already searches LinkedIn and scores
matches with Claude, but it's only reachable via the CLI / A2A chat endpoint — there's no
REST route and no UI. Separately, search is LinkedIn-only; Rohit wants to widen it to
Greenhouse and Lever job boards, which (unlike Workday/Taleo) expose clean, scrapeable
public listing pages with no login wall.

Two things confirmed during scoping that change the shape of this work:
- The agent uses the Tavily search API (`include_domains=["linkedin.com"]`), **not**
  Playwright — there is no browser automation in the search path today.
- `output/jobs/{jobs,seen_jobs,applied_jobs}.json` are global files, not scoped per
  profile. This was fine with one profile (`rohit`) but is a latent bug now that a second
  profile (`malini-aishwarya-batchu`) exists — a search run for one profile would
  overwrite state for the other.

## Goals

1. Widen job search to cover LinkedIn + Greenhouse + Lever, using the same
   Tavily-search-and-Claude-score approach already in place — no per-company target list,
   no direct ATS API calls, no scraping of Workday/Taleo.
2. Make job-search results and the "search now" action available from the web UI.
3. Fix the per-profile storage bug as part of this work, since the new REST routes are
   profile-scoped and would otherwise inherit the same bug.

## Non-goals

- Auto-submitting applications into any ATS (LinkedIn Easy Apply or otherwise). That
  remains a separate, deferred piece of work — see `project_auto_apply` memory.
- Workday/Taleo scraping. No public listing API or clean search-indexable page structure;
  revisit only if specifically requested.
- Scheduled/cron search runs. Manual "Search now" trigger only, for this iteration.
- Calling the Greenhouse/Lever board JSON APIs directly. Search-based discovery is the
  full v1 scope; direct API calls are a future option if search-based discovery proves too
  noisy in practice.

## Design

### 1. Agent changes — `agents/job_search_agent.py`

- Rename the `search_linkedin_jobs` tool to `search_job_boards`; change
  `include_domains` from `["linkedin.com"]` to
  `["linkedin.com", "boards.greenhouse.io", "jobs.lever.co"]`.
- Update the hard "LinkedIn jobs only" result filter and the system prompt's discard rule
  ("Any domain other than linkedin.com") to accept all three domains.
- Add search angles for the two new domains to the system prompt (mirroring the existing
  LinkedIn role/skill angle instructions), e.g.
  `site:boards.greenhouse.io <role> <skill>` / `site:jobs.lever.co <role> <skill>`.
  Raise the search budget from "exactly 10" searches to spread across three domains
  (system prompt instruction, not a code constant).
- `read_job_page` (Tavily `extract`) is already domain-agnostic — no change needed there.
- Each returned job record gets a `source` field: `linkedin` / `greenhouse` / `lever`,
  derived from the URL's domain (not asked of the model — computed in code after scoring,
  so it can't be hallucinated).

### 2. Storage — per-profile, persistent, merged

Move output from `output/jobs/*.json` to `output/profiles/{slug}/jobs.json` — one file
per profile, consistent with how `search_brief.json` and `resume_data.json` are already
scoped.

Replace the current three-file (`jobs.json` / `seen_jobs.json` / `applied_jobs.json`)
overwrite model with a single merged, persistent store:

```json
{
  "generated_at": "2026-07-17T10:00:00+00:00",
  "candidate": "Rohit Vishnu Mopuri",
  "jobs": {
    "<12-char id, sha1(url) truncated>": {
      "id": "...",
      "source": "greenhouse",
      "title": "...",
      "company": "...",
      "location": "...",
      "url": "...",
      "relevance_score": 8,
      "match_reason": "...",
      "status": "new",
      "first_seen_at": "2026-07-17T10:00:00+00:00",
      "last_seen_at": "2026-07-17T10:00:00+00:00"
    }
  }
}
```

Merge rule for each search run, per job found:
- Not in store yet → add with `status: "new"`.
- Already in store with `status` in `("new", "seen")` → refresh `relevance_score`,
  `match_reason`, `last_seen_at`; leave `status` as-is (still actionable).
- Already in store with `status` in `("applied", "dismissed")` → refresh
  `last_seen_at` only; leave everything else untouched (don't resurface something the
  user already dealt with).

Jobs already in the store that were *not* found in the current run are left alone (no
expiry logic — a job might not resurface simply because it dropped out of Tavily's top
results, not because it closed).

`status` transitions to `"seen"` the first time it's returned via the read-listing API
(so the UI can distinguish "brand new since last visit" from "already looked at, still
open"). `mark_applied` / a new `mark_dismissed` set `applied` / `dismissed` directly.

This replaces `agents/job_search_agent.py`'s `mark_applied()` free function's file target
and the `run()` function's tail-end save logic (currently lines ~350–384). The
email-on-new-jobs side effect is unchanged (still fires for records that entered this run
as `status: "new"`).

### 3. Backend API — new `a2a/routes/job_search.py`

Same background-task + polling convention as `a2a/routes/search_brief.py`:

- `POST /api/profiles/{slug}/job-search` — starts `job_search_agent.run()` as a
  `BackgroundTasks` job. Returns `{"status": "searching"}`. If a search for that slug is
  already running, returns `409 Conflict` (tracked via an in-memory `set` of in-flight
  slugs — single-process app, no need for anything heavier).
- `GET /api/profiles/{slug}/job-search` — returns `{"status": "searching"}` while running,
  otherwise `{"generated_at", "jobs": [...]}` — the merged store's jobs as a list, sorted
  by `relevance_score` desc, excluding `status: "dismissed"`.
- `POST /api/profiles/{slug}/job-search/{job_id}/apply` — sets `status: "applied"`.
- `POST /api/profiles/{slug}/job-search/{job_id}/dismiss` — sets `status: "dismissed"`.

Router registered in `a2a/server.py` alongside the existing four.

### 4. Frontend

- `web/lib/types.ts` — add `JobMatch` interface matching the record shape above.
- `web/lib/api.ts` — add `searchJobs(slug)`, `getJobMatches(slug)`, `applyToJob(slug, id)`,
  `dismissJob(slug, id)`.
- New page `web/app/jobs/page.tsx`:
  - Header: "Jobs" + match count, mirroring `applications/page.tsx`'s header pattern.
  - "Search now" button — same disabled-while-polling UX as the Tailor and Search Brief
    pages (poll `GET .../job-search` every few seconds while `status === "searching"`).
  - Job list sorted by score desc: title / company / location, a small source badge
    (LinkedIn / Greenhouse / Lever — reuse the `StatusBadge.tsx` pattern for a coloured
    pill), match reason, score, and View (opens `url` in a new tab) / Applied / Dismiss
    actions. Applied/Dismissed jobs drop out of view immediately (client-side removal from
    the list on success, no full refetch needed).
  - Empty state: "Select a profile first" (no profile) or "No matches yet — click Search
    now" (profile selected, empty list) — same tone as `applications/page.tsx`.
- Add "Jobs" entry to `web/components/TopNav.tsx`'s nav array.

### 5. Testing

TDD, red-green-refactor, real behaviour over mocks except at the genuine external
boundary (Tavily + Anthropic API calls):

- **Merge logic** (pure function, extracted so it's testable without network calls):
  unit tests for each transition (`new` job, refreshed `new`/`seen` job, untouched
  `applied`/`dismissed` job).
- **Domain filter**: feed a mixed list of URLs (linkedin/greenhouse/lever/other), assert
  only the three target domains survive and `source` is correctly derived.
- **Routes**: monkeypatch `job_search_agent.run` so route tests exercise the
  background-task wiring, 409-on-concurrent-search, and the apply/dismiss status
  transitions against a real temp-directory profile store — without hitting real APIs.
- **Feedback summary**: unit test `build_profile_summary()`'s new section against a
  fixture store — asserts applied/dismissed entries appear, oldest-beyond-N are dropped,
  and an empty store (no history yet) omits the section entirely rather than printing
  "Recent signal: none".

### 6. Feedback loop — bias future search on applied/dismissed history

Prompted by looking at how Jack & Jill (a two-sided AI recruiting product) improves its
matching: candidates give it a yes/no on each suggestion, and that revealed preference
shapes what it surfaces next. Most of that product doesn't transfer — its ATS
integration is on the *employer* side (official platform access to pull requisitions
from Greenhouse/Lever/Workday/SuccessFactors), not something a search-based personal
tool can replicate, and there's no published detail on its actual matching algorithm
beyond marketing language. The one transferable idea is the feedback loop itself, which
needs no new infrastructure given the persistent store already in this design (section 2)
already records `applied`/`dismissed` status per job.

Change to `build_profile_summary()`: before building the prompt, read the profile's job
store and pull the most recent N (suggest N=10) `applied` and N `dismissed` records.
Append a short section to the prompt:

```
Recent signal from past search runs:
Applied to (positive signal — find more like these): <title @ company>, ...
Dismissed (negative signal — avoid these patterns): <title @ company — reason if known>, ...
```

This is a heuristic prompt addition, not a trained model — it rides on Claude's existing
scoring judgement rather than adding a ranking layer. Cap at N=10 each so the prompt
doesn't grow unbounded over time; drop the oldest once a status list exceeds that.

## Open questions / risks

- Tavily's search index coverage of Greenhouse/Lever postings is unproven — it may
  surface far fewer results than LinkedIn, or none for some role/skill angles. This is a
  "try it and see" risk inherent to the search-based (not direct-API) approach chosen for
  v1; the fallback if it's too sparse is calling the Greenhouse/Lever public JSON APIs
  directly against a curated company list (explicitly out of scope for now).
- The feedback loop (section 6) is unvalidated — it's plausible that a handful of
  dismissed examples usefully steers the model away from a pattern, but this could also
  have no measurable effect, or overcorrect (e.g. one dismissed role tanking an entire
  adjacent category). Worth a manual before/after comparison once built rather than
  assuming it works as intended.
