# Job fit features: design

Date: 2026-10-20
Status: approved 2026-10-20
Depends on: [Bauhaus-lite redesign](2026-10-20-bauhaus-redesign-design.md). Build that first, so every new screen
uses the new visual system.

## Intent

Rohit needs an honest picture of how well he fits each job and what to do about the
gaps, without the app being strict. Job descriptions pile on requirements, and he
often applies when the fit isn't complete. The app should advise, never block.

The features put into the app the three prompts he already uses by hand (quoted in full in the
appendix): decoding the job ad, scoring him honestly against it, and tailoring
within strict truthfulness rules.

## Goals

1. **Job analysis.** Decode the job ad and score Rohit against its real requirements.
2. **Match score.** A 0–100 number computed from that analysis, weighted towards the
   requirements most likely to be real filters.
3. **Truthful tailoring.** Tailor under Rohit's may and may-not rules, list every change,
   and flag any claim that wasn't in the base resume.
4. **ATS view.** Show what an applicant tracking system extracts from the tailored PDF, and which important terms
   didn't come through.
5. **Follow-ups.** Follow-up dates on applications, with overdue ones surfaced.

## Non-goals

- Blocking or discouraging tailoring or applying because of a low score. Results
  are advice, shown **after** tailoring.
- Running the full analysis on every job from a search. (Rohit's decision. See "Two tiers".)
- Auto-applying, sending emails or any outreach.
- Changing the resume PDF template.

## Anti-goals

- A score so strict that every realistic job looks like a poor fit. That would
  make the feature useless to him.
- Inventing analysis from a two-line search snippet and presenting it as if it came
  from the full ad.
- Tailoring that quietly adds claims, scope or titles he didn't have.

## Two tiers of analysis (Rohit's decision)

**Tier 1, triage. Every job a search suggests gets it.** The existing scoring call in
`agents/job_search_agent.py` already rates each job with Claude. Extend its output
for each job with:
- `red_flags`: obvious blockers stated in the text, such as "no visa sponsorship",
  "security clearance required" or "on-site 5 days in a city he hasn't selected".
- `text_basis`: `"full"` if the agent read the job page, `"snippet"` otherwise.

There are no extra API calls; this extends the existing prompt and output schema. *(My
call. It's cheaper than a separate Haiku pass and gives the same result.)*

**Tier 2, full analysis. Runs only when Rohit shows interest:**
- He clicks **analyse** on a job card on the Jobs page, or
- he tailors for a job (tailoring reuses a saved analysis, or runs one first).

The full analysis fetches the complete ad (with the existing `fetch_job_description`,
Playwright fallback included), then runs prompts 1 and 2 with Sonnet (`MODEL` from
`core/config.py`). It runs as a background task with polling, following the existing
pattern in `tailor_api.py`.

**Caching.** Analyses are saved to `output/profiles/{slug}/analyses/{analysis_id}.json`.
`analysis_id` is a hash of the normalised job text plus the hash of the base resume
used. The same ad with the same resume is never analysed twice. If the base resume
changes, the next request produces a fresh analysis. A job store entry and a tailor
run each record the `analysis_id` they used.

## Analysis contents

Structured JSON from Claude. The model is asked for these fields:

**From prompt 1 (decode):**
- `what_it_really_is`: a short paragraph
- `problem_being_solved`: a paragraph, including what that suggests went wrong before
- `search_terms`: a list of exact phrases taken from the ad
- `suspicious`: a list of contradictions, impossible skill mixes, or signs the role was written around an existing person
- `requirements`: a list ranked by how likely each is to be a real filter. Each item:
  `text`, `filter_likelihood` (`high` | `medium` | `low` | `filler`), `why`, `key_terms`

**From prompt 2 (score), per requirement that isn't filler:**
- `meets` (`yes` | `partly` | `no`), `evidence` (quoted from the resume, or empty), `interview_answer`

**Overall:**
- `gaps_that_matter` (exactly 3, or fewer if there are fewer), `gaps_that_dont`
- `verdict` (`strong fit` | `genuine stretch` | `waste of time`), `verdict_reason`
- `left_off`: things that are true and relevant but missing from the resume, phrased as questions
  for Rohit to confirm ("Did you lead the Kafka migration?") and never stated as fact

## Match score (deterministic, from the analysis)

Calculated in Python, not by the model, so that it's consistent and testable:

- Weights: high = 3, medium = 2, low = 1, filler = 0 (excluded).
- Credit: yes = 1, partly = 0.5, no = 0.
- `score = round(100 × Σ(weight × credit) / Σ(weight))`, or no score when there are no
  scorable requirements.
- Shown in the redesign's primary colours: 70 or more is blue, 45–69 is yellow, under 45 is red.
  *(My call on the cut-offs. Low is red but never stops anything.)*

The score measures the **base resume** against the job, because tailoring rewords
what's there and doesn't change the truth. The score is stored on the analysis, and
copied onto an application when one is created from a tailor run.

## Truthful tailoring

1. **Replace the rules** in `tailor_resume()` (`agents/tailor_agent.py`) with prompt 3's
   *may* and *may not* lists, word for word. Keep the existing "do not change name, titles,
   companies, dates…" constraints and `HUMANISE_RULES`. Give the analysis's
   high and medium requirements and `search_terms` as context, so the tailoring targets the real filters.
2. **Change log.** The tailoring response becomes `{ "resume": {...}, "changes": [...] }`.
   Each change has: `section`, `before`, `after`, `kind` (`reordered` | `reworded` |
   `expanded` | `shrunk` | `summary` | `skills`) and `needs_confirmation` (bool), plus `reason`.
3. **Fabrication check (deterministic, in Python, runs on the final resume after the humanise
   pass):** compare the tailored resume with the base resume and flag anything in the
   tailored version that doesn't appear in the base:
   - numbers and metrics (percentages, currency amounts, counts, durations)
   - entries in the skills lists
   - capitalised technology or product names in bullets and the summary
   - any change to a title, company or date (the prompt forbids this anyway; this is the safety net)

   Each flag says where it was found and what the text was. False positives are acceptable,
   because flags are things to confirm, not errors. The humanise pass runs after tailoring, so
   only this check sees the final wording.

The change log, flags and `analysis_id` are saved with the tailor output (`meta_{id}.json`
or a sidecar next to it), so the history list can show the score and verdict, and so the
hand-edit re-check has what it needs.

## ATS view (deterministic)

After the PDF is rendered, extract its text with `pdfplumber` (already a dependency) in
reading order and save it. Checks:
- contact details found (email and phone patterns)
- standard section headings found (summary, experience, skills, education)
- each `search_terms` phrase, and the key terms from high-likelihood requirements, shown as
  **present** or **missing** in the extracted text (case-insensitive)

## Follow-ups

- New nullable columns on `applications`: `follow_up_date` (ISO date), `match_score`
  (int), `analysis_id` (text). Add them in `init_db()` with `ALTER TABLE … ADD COLUMN` when missing.
  The existing database must keep working.
- When status changes to `applied` and `follow_up_date` is empty, set it to applied date + 7 days.
  *(My call on 7 days.)* It can be edited in the tracker.
- **Overdue** means status is `applied` or `interview`, and `follow_up_date` is today or earlier.
- Actions: **followed up**, which moves the date 7 days later, and **clear**.

## UI (in the new visual system)

**Tailor result (`/tailor`)**, below the existing completed-job view, as titled sections separated by rules:
1. **Verdict**: score (large number with a colour marker), verdict and reason, the 3 gaps that
   matter, and a collapsible list of gaps that don't.
2. **Requirements**: a table of rank, requirement, filter likelihood, meets marker, evidence,
   and interview answer (expandable).
3. **Changes**: the change log. Rows with `needs_confirmation` and every fabrication flag carry a
   red marker and sit at the top.
4. **Left off**: questions to confirm.
5. **ATS view**: checks list and present/missing terms, plus the extracted text in a
   monospace block.
6. **About this job**: what it really is, problem being solved, suspicious signs.

**Jobs page (`/jobs`)**: each card shows the triage `red_flags` (red markers) and a
`snippet` / `full` label. An **analyse** button starts tier 2. Once finished, the card
shows the score and verdict, and expands to the same Verdict, Requirements and About sections.

**Applications (`/applications`)**: a match score column, a follow-up column (overdue
in red), and the followed-up and clear actions. Kanban cards show an overdue marker.

**Dashboard**: the summary line becomes "N applications need a follow-up". The
*average match* stat block appears once any application has a score. Recent application
rows show the score.

**History (dashboard tailored-resumes list)**: entries with a saved analysis show the score
and verdict. Past runs do **not** reopen the full result view; downloads only, as today.
(Rohit's decision. The full result is available while the tailor job is held in server memory.)

## Constraints

- Python 3.9 typing (`Optional`, `List`, `Dict`).
- `MODEL` imported from `core/config.py`. JSON parsed with `extract_json_object`.
- Long AI calls run as background tasks with polling. No request blocks for more than about 10s.
- New endpoints go in `web/lib/api.ts`, new types in `web/lib/types.ts`.
- Slugs and IDs are validated against path traversal, as the existing routes do.
- Test first for the deterministic parts: score calculation, fabrication check,
  ATS checks, follow-up date rules, the database migration, and the cache key. API tests use FastAPI's
  TestClient. The Anthropic call is mocked, since it's the external boundary.

## Settled after builder review (my calls; check these)

- **Build order.** The redesign is part of the same plan and comes first. The feature UI is built
  directly in the new system.
- **Change log vs humanise pass.** Keep the humanise pass. Tailoring returns changes keyed by
  location (`summary`, `skills`, or `experience[i].description[j]`). After humanising, Python
  replaces each change's `after` text with the final wording at that location, so the log
  always matches the PDF.
- **Key terms.** The analysis returns `key_terms` (a short list of exact phrases from the ad) for each
  requirement. The ATS check stays deterministic and uses these together with `search_terms`.
- **Base resume for the fabrication check.** Each tailor run saves a copy of the base resume
  it used, next to its other files. The check compares against that copy, not
  the current `resume_data.json`.
- **Hand edits.** Saving a hand-edited tailored resume (`PATCH /api/tailor/{job_id}/data`)
  re-runs the fabrication check and the ATS view, because both are cheap and deterministic. A claim added by
  hand gets flagged like any other.
- **Applied date.** Creating an application as `applied`, or moving one to `applied`, sets
  `applied_date` to today if it's empty. `follow_up_date` is then applied date + 7 days. **Clear**
  needs an explicit null on PATCH, so the patch model must tell "not sent" apart from "null".
- **Left off.** Display only. Rohit adds anything he confirms through the existing
  resume edit page.
- **Job text length.** Raise the 4,000-character limit in `fetch_job_description` to
  20,000, so that requirements near the end of long ads aren't lost. This also applies to
  tailoring.

## Left to the builder

- Exact prompt wording around Rohit's quoted prompts, and the JSON schema field order.
- How the job text is normalised for the cache hash.
- Component breakdown, spacing and copy within the redesign rules.

## Appendix: Rohit's prompts, verbatim

**Prompt 1: decode the job ad**
> Tell me:
> - what this job actually is, underneath the language
> - which requirements are real and which are filler pasted from an old ad
> - what problem they are hiring to solve, and what that suggests went wrong before
> - the exact words someone would search for, taken from this ad
> - anything suspicious: contradictions, an impossible mix of skills, signs the role was written around someone they already have
>
> Rank the requirements by how likely each is to be a real filter.

**Prompt 2: score me**
> Score me honestly. For each real requirement, tell me:
> - do I meet it, partly meet it, or not at all
> - what in my resume backs that up
> - what I would say in an interview about the gap
>
> Then tell me:
> - the three gaps that matter, and which ones do not
> - whether this is a genuine stretch or a waste of my time
> - what I could truthfully add that I have simply left off
>
> Be blunt.

**Prompt 3: tailor**
> Tailor my resume for this job.
>
> You may:
> - reorder bullets so the relevant ones come first
> - change wording so my real work is described in their language
> - expand a bullet that matters here and shrink one that does not
> - adjust my summary and skills list to match what this job is about
>
> You may not:
> - add new claims, bigger scope, or titles I did not hold
> - stuff in keywords, or list a skill I could not be tested on
>
> At the end, list every change you made and mark the ones I need to confirm are accurate.
