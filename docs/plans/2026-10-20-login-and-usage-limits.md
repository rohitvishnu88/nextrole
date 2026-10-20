# Login and Usage Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google sign-in for invited friends, give each user private data, meter every Claude and Tavily call per user per month, and enforce a hard $50 monthly ceiling. Keep A2A available behind a bearer token.

**Architecture:**
- **Sign-in:** FastAPI handles Google OAuth with Authlib, and keeps the session in a signed cookie through Starlette's `SessionMiddleware`.
- **Data scoping:** every `/api` route depends on `current_user` and checks ownership with a single `require_profile`.
- **Metering:** all AI and Tavily clients are created by one factory in `core/ai_clients.py`. It records each call into a usage ledger (`core/usage.py`, in the same SQLite database). Actions reserve an estimated cost first, commit with the measured cost, or release on failure.

**Tech Stack:** Python 3.9, FastAPI, Authlib, itsdangerous, httpx, SQLite, Anthropic SDK, Tavily; Next.js 14.

**Spec:** `docs/specs/2026-10-20-login-and-usage-limits-design.md`

## Global Constraints

- **Python 3.9 typing** only: `Optional[...]`, `List[...]` and `Dict[...]`.
- **Model names come from `core/config.py`.** `MODEL` stays there; add `HAIKU_MODEL = "claude-haiku-4-5-20251001"` there too, and use it in `a2a/routes/search_brief.py` instead of the hardcoded string.
- **No secrets** in code, tests, docs or commits. These environment variables are documented in the README with placeholder names only: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET`, `PUBLIC_BASE_URL`, `OWNER_EMAIL`, `ALLOWED_EMAILS`, `A2A_TOKEN`.
- **Package imports for the shared modules.** Import `core.usage` and `core.ai_clients` as packages everywhere, agents included. The agents add the repo root to `sys.path`. Never import them as bare `usage` or `ai_clients`. Two module copies would split the context variable and the ledger, and calls would go unmetered.
- **Allowances per user per month:** `job_search` 4, `tailor` 12, `analyse` 15, `section_draft` 20, `resume_parse` 3, `search_brief` 3. **`MONTHLY_BUDGET_USD = 50`**.
- **Estimated hold per action**, in USD: `job_search` 0.60, `tailor` 0.30, `analyse` 0.10, `section_draft` 0.03, `resume_parse` 0.05, `search_brief` 0.01, `cli` 0.30.
- **Months are calendar months in UTC**, stored as `"YYYY-MM"`. `resets_on` is the 1st of next month.
- **Session cookie:** HttpOnly, `SameSite=Lax`, max age 30 days. It's `Secure` when `PUBLIC_BASE_URL` starts with `https://`.
- **Hidden resources return 404.** A resource owned by another user returns 404, never 403.
- **Running tests:** run each task's tests with `python3 -m pytest tests/<file>.py -v`. Never run bare `pytest tests/`; the full run uses `--ignore=tests/test_tailor.py`.
- **Mocks** are allowed only for Google's endpoints, Anthropic, Tavily and DNS resolution.
- **Frontend:** `cd web && npm run typecheck` must exit 0.

## Review Focus

1. **A session cookie that outlives an allowlist removal.** The next request must get 401 or 403 "not invited", not data. Pinned in Task 1.
2. **Two users with the same slug.** If friend B uploads a resume named "Rohit", the slug collides with Rohit's `rohit` folder. Creation must pick a unique slug and never write into someone else's folder. Pinned in Task 2.
3. **A background thread loses the reservation.** Tailoring and search run in executor threads. A call made there must still be metered against the right reservation, never against the CLI owner. Pinned in Task 5.
4. **Several users at once, just under the ceiling.** In-flight holds must block the extra actions. Pinned in Task 4.
5. **A URL that resolves to a private address, or redirects to one.** For example `http://169.254.169.254/` or a public page that redirects to `http://localhost:8000`. It must be refused before any fetch. Pinned in Task 8.

---

### Task 1: Users, Google sign-in, session, allowlist

**Files:**
- Create: `a2a/auth.py`, `tests/auth_helpers.py`, `tests/test_auth_api.py`
- Modify: `a2a/db.py` (users table), `a2a/server.py` (session middleware and auth router), `requirements.txt`, `README.md` (environment variables)

**Interfaces:**
- **Produces:**
  - `User` dataclass: `id: str, email: str, name: str, picture: str, is_owner: bool`.
  - In `db`: `upsert_user(email, name, picture, is_owner) -> dict`, `get_user(user_id) -> Optional[dict]`, `list_users() -> List[dict]`.
  - In `auth`:
    - `allowed_emails() -> set`: `ALLOWED_EMAILS` plus `OWNER_EMAIL`, lowercased and stripped.
    - `is_allowed(email: str) -> bool`.
    - `current_user(request: Request) -> User`, a FastAPI dependency. It returns 401 if there's no session or the user is unknown, and 403 `{"code": "not_invited"}` if the email is no longer allowed.
    - `router` with these routes:
      - `GET /api/auth/login`: redirects to Google.
      - `GET /api/auth/callback`:
        - on success, sets `session["user_id"]` and redirects to `PUBLIC_BASE_URL + "/"`;
        - for an email that isn't allowed or verified, redirects to `/?auth_error=not_invited&email=<urlencoded>` and creates no user;
        - on an OAuth error, redirects to `/?auth_error=failed`.
      - `POST /api/auth/logout`: clears the session.
      - `GET /api/auth/me`: returns `{email, name, picture, is_owner}`.
  - In `tests/auth_helpers.py`:
    - `OWNER = User("u-owner", "owner@example.com", "Owner", "", True)` and `FRIEND = User("u-friend", "friend@example.com", "Friend", "", False)`.
    - `sign_in(app, user)` sets `app.dependency_overrides[auth.current_user]`.

- [ ] **Step 1: Write the failing tests** in `test_auth_api.py`. Mock `auth.oauth.google.authorize_access_token` to return `{"userinfo": {...}}`.
  - `test_callback_creates_user_and_session_for_allowed_email`: the `/api/auth/me` that follows returns the email.
  - `test_callback_rejects_uninvited_email`: redirect to `auth_error=not_invited`, and `db.list_users() == []`.
  - `test_callback_rejects_unverified_email`
  - `test_me_401_without_session`
  - `test_removed_from_allowlist_gets_403_on_next_request`: sign in, then monkeypatch `ALLOWED_EMAILS` without the email, then `/me` returns 403 `not_invited`.
  - `test_logout_clears_session`
  - `test_owner_flag_from_owner_email`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_auth_api.py -v`. Expected: FAIL (module not found).
- [ ] **Step 3:** Implement it. Add `authlib`, `itsdangerous` and `httpx` to `requirements.txt` and install them. Register the Google provider with `server_metadata_url="https://accounts.google.com/.well-known/openid-configuration"` and `client_kwargs={"scope": "openid email profile"}`. Add `SessionMiddleware(secret_key=SESSION_SECRET, same_site="lax", https_only=<https>, max_age=30*24*3600)`. Refuse to start if `SESSION_SECRET` is unset, except when `TESTING=1`.
- [ ] **Step 4:** Run the same command. Expected: 7 passed.
- [ ] **Step 5:** Commit: `feat: add Google sign-in with invite allowlist and session cookie`.

### Task 2: Profile ownership and scoping (profiles, resume, versions, search brief)

**Files:**
- Create: `a2a/ownership.py`, `tests/test_ownership_api.py`
- Modify: `a2a/routes/profiles.py`, `a2a/routes/resume_versions.py`, `a2a/routes/search_brief.py`, `a2a/server.py` (startup migration), and the existing test fixtures in `tests/test_profiles_api.py`, `tests/test_resume_versions_api.py` and `tests/test_search_brief_api.py` (add `sign_in(app, OWNER)`)

**Interfaces:**
- **Consumes:** `current_user` and `User` from Task 1.
- **Produces:**
  - `ownership.MAX_PROFILES_PER_USER = 3`.
  - `owner_of(profile: dict) -> Optional[str]`.
  - `visible_profiles(user: User) -> List[dict]`. A profile with no `owner_user_id` is visible only to the owner.
  - `require_profile(slug: str, user: User) -> dict`. It raises 400 for an invalid slug, and 404 if the profile is missing or not the user's.
  - `assign_unowned_to(owner_user_id: str) -> int`. Run at startup once the owner user exists, and after the owner's first sign-in.
  - `unique_slug(base: str) -> str`. It appends `-2`, `-3` and so on when the base slug is already taken, by anyone.
- **Route behaviour:**
  - `GET /api/profiles` returns only `visible_profiles(user)`.
  - `POST /api/profiles` stamps `owner_user_id`, uses `unique_slug`, and returns 409 `{"code": "profile_limit"}` when a non-owner already has 3.
  - Every `/{slug}…` route in the three routers calls `require_profile` first.

- [ ] **Step 1: Write the failing tests.** Two users, using `FRIEND` and a second `User("u-b", …, False)`.
  - `test_friend_sees_only_own_profiles`
  - `test_other_users_profile_is_404` across GET resume, PATCH, DELETE, resume history, section draft and apply, search-brief GET and generate.
  - `test_unowned_profile_visible_to_owner_only`
  - `test_create_with_taken_slug_gets_unique_slug`: friend creates "Rohit" while `rohit` exists, gets slug `rohit-2`, and the `rohit/` folder is untouched.
  - `test_profile_limit_for_friend_not_owner`
  - `test_assign_unowned_to_owner`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_ownership_api.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement it. Add `user: User = Depends(current_user)` to every handler in the three routers, and update the existing fixtures to `sign_in(app, OWNER)`.
- [ ] **Step 4:** Run `python3 -m pytest tests/test_ownership_api.py tests/test_profiles_api.py tests/test_resume_versions_api.py tests/test_search_brief_api.py -v`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: scope profiles, resume and search brief routes to their owner`.

### Task 3: Scoping for job search, job analysis, tailor and applications

**Files:**
- Modify: `a2a/routes/job_search.py`, `a2a/routes/job_analysis.py`, `a2a/routes/tailor_api.py`, `a2a/routes/applications.py`, the matching existing test fixtures, and `tests/test_ownership_api.py`
- Create: `scripts/__init__.py`, `scripts/assign_profile.py`

**Interfaces:**
- **Consumes:** `require_profile` and `visible_profiles` from Task 2.
- **Produces:**
  - Tailor `_jobs[job_id]["user_id"]`. Every `/{job_id}…` tailor route returns 404 unless it matches. `POST /api/tailor` calls `require_profile(body.profile_slug, user)`.
  - Applications:
    - `GET ?profile=` and `POST` require the profile;
    - `PATCH`, `DELETE` and `followed-up` load the row and require its `profile_id`.
  - `python3 -m scripts.assign_profile <slug> <email>` sets `owner_user_id` to that user's id. It exits non-zero if the user hasn't signed in yet.
  - Job search email: in `a2a/routes/job_search.py::_run_search`, pass `send_email=user.is_owner` into `job_search_agent.run(..., send_email: bool = True)`.

- [ ] **Step 1: Write the failing tests** in `test_ownership_api.py`:
  - `test_other_users_job_search_and_analysis_404`
  - `test_other_users_tailor_job_404`: seed `_jobs` with `user_id="u-b"` and call `/api/tailor/{id}`, `/data`, `/fit`, `/pdf` and PATCH `/data` as `FRIEND`.
  - `test_other_users_application_404_on_patch_delete_followup`
  - `test_friend_search_does_not_email`: monkeypatch `job_search_agent.run` to capture `send_email`.
  - `test_assign_profile_script_moves_profile`
- [ ] **Step 2:** Run the new tests. Expected: FAIL.
- [ ] **Step 3:** Implement it, and update the existing fixtures in `test_job_search_api.py`, `test_job_analysis_api.py`, `test_tailor_edit_api.py`, `test_tailor_history_api.py` and `test_applications_api.py` to `sign_in(app, OWNER)`.
- [ ] **Step 4:** Run `python3 -m pytest tests/test_ownership_api.py tests/test_job_search_api.py tests/test_job_analysis_api.py tests/test_tailor_edit_api.py tests/test_tailor_history_api.py tests/test_applications_api.py -v`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: scope job search, analysis, tailor and applications to their owner`.

### Task 4: Usage ledger (`core/usage.py`)

**Files:**
- Create: `core/__init__.py` (if missing), `core/limits.py`, `core/usage.py`, `tests/test_usage.py`

**Interfaces:**
- **Produces:**
  - In `limits`: `ACTION_LIMITS`, `ACTION_ESTIMATES_USD` and `MONTHLY_BUDGET_USD` (values from Global Constraints), plus the `PRICES` per model and `TAVILY_CREDIT_USD = 0.008`. The builder verifies current published prices and notes the date in a comment.
  - In `usage`:
    - `month_of(now: datetime) -> str` and `resets_on(month: str) -> str`.
    - `class LimitReached(Exception)` with `code` (`"limit_reached"` | `"budget_reached"`), `action` and `resets_on`.
    - `reserve(user_id: Optional[str], action: str, is_owner: bool, now=None) -> str`. Returns the reservation id, and raises `LimitReached` per the spec.
    - `record_call(reservation_id: Optional[str], *, model: str = "", input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0, tavily_credits=0) -> None`. Adds the measured cost to the reservation.
    - `commit(reservation_id)` and `release(reservation_id)`.
    - `spent_this_month(now=None) -> float`, which is committed plus released measured cost, plus the estimates for reservations still in flight.
    - `counts_for(user_id, month) -> Dict[str, int]`, which counts reserved and committed.
    - `summary(month) -> dict`, which gives per-user and per-action spend for the owner view.
  - A `usage` table in the applications database, keyed as the spec describes, plus `estimate_usd`.
  - Ceiling rule: refuse if `spent_this_month() + ACTION_ESTIMATES_USD[action] > MONTHLY_BUDGET_USD`.

- [ ] **Step 1: Write the failing tests** (temporary database through `APPLICATIONS_DB`, as in `test_applications_api.py`):
  - `test_reserve_until_user_limit_then_limit_reached`: 4 `job_search` reservations succeed, and the 5th raises `code == "limit_reached"`.
  - `test_owner_exempt_from_user_limit`
  - `test_release_does_not_count_against_allowance_but_cost_counts_to_budget`
  - `test_in_flight_estimates_block_budget`: five users each hold `job_search` at the 0.60 estimate with $47.50 committed, so the next reserve raises `budget_reached`. Pins Review Focus 4.
  - `test_commit_replaces_estimate_with_measured_cost`
  - `test_record_call_prices_tokens_and_tavily_credits`, against a known `PRICES` entry
  - `test_month_rollover_resets_counts`, with `resets_on("2026-12") == "2027-01-01"`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_usage.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement it. Run reserve inside a single `BEGIN IMMEDIATE` transaction, so two concurrent reserves can't both pass the checks.
- [ ] **Step 4:** Run the same command. Expected: 7 passed.
- [ ] **Step 5:** Commit: `feat: add usage ledger with per-user limits and a hard monthly ceiling`.

### Task 5: Metered client factory, replacing every construction site

**Files:**
- Create: `core/ai_clients.py`, `tests/test_ai_clients.py`
- Modify: `agents/tailor_agent.py`, `agents/job_search_agent.py`, `agents/linkedin_agent.py`, `agents/job_freshness.py` (if it builds a client), `a2a/routes/job_analysis.py`, `a2a/routes/search_brief.py`, `a2a/routes/resume_versions.py`, `a2a/routes/profiles.py`

**Interfaces:**
- **Consumes:** `usage.record_call`, `usage.reserve` and `usage.commit` from Task 4.
- **Produces:**
  - `ai_clients.metered(reservation_id: str)`, a context manager that sets a `ContextVar`. It must be entered **inside** the worker thread or background function, not before handing off.
  - `make_anthropic() -> MeteredAnthropic`. Its `.messages.create(**kw)` forwards to the real client, then calls `record_call` with `response.usage` and `kw["model"]`.
  - `make_tavily() -> MeteredTavily`. Its `.search(...)` and `.extract(...)` forward the call, then record credits: search basic is 1, advanced is 2; extract is 1 per 5 URLs, rounded up.
  - **When no reservation is active (CLI):** before each call, `reserve(None, "cli", True)`. That raises `budget_reached` at the ceiling. After the call, `record_call` and then `commit`.
- **Afterwards:** grep for `anthropic.Anthropic(` and `TavilyClient(` outside `core/ai_clients.py` must return nothing.

- [ ] **Step 1: Write the failing tests.** Fake inner clients, injected via `ai_clients._real_anthropic` and `_real_tavily` factories that the tests monkeypatch.
  - `test_call_inside_metered_records_against_reservation`
  - `test_call_in_worker_thread_with_metered_inside_thread_records_correctly`: run through `loop.run_in_executor` with `metered` entered in the thread. Pins Review Focus 3.
  - `test_call_without_reservation_is_cli_and_refused_at_ceiling`
  - `test_tavily_credits_recorded`
  - `test_no_direct_client_construction_left`: a grep-style test that scans `agents/`, `a2a/` and `core/` source for `anthropic.Anthropic(` and `TavilyClient(` outside `core/ai_clients.py`.
- [ ] **Step 2:** Run `python3 -m pytest tests/test_ai_clients.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the factory and replace all construction sites. In the agents, add the repo root to `sys.path` and use `from core.ai_clients import make_anthropic, make_tavily`.
- [ ] **Step 4:** Run `python3 -m pytest tests/test_ai_clients.py tests/test_tailor_fit.py tests/test_job_analysis.py tests/test_job_analysis_api.py tests/test_search_brief_api.py tests/test_resume_versions_api.py tests/test_profiles_api.py -v`. Expected: all pass. Update the monkeypatches that targeted `anthropic.Anthropic` so they target `ai_clients._real_anthropic`.
- [ ] **Step 5:** Commit: `feat: route every Claude and Tavily call through a metered client`.

### Task 6: Reserve, commit or release around each action, with 429s

**Files:**
- Create: `a2a/metering.py`, `tests/test_limits_api.py`
- Modify: `a2a/routes/job_search.py`, `a2a/routes/job_analysis.py`, `a2a/routes/tailor_api.py`, `a2a/routes/resume_versions.py` (draft), `a2a/routes/profiles.py` (parse), `a2a/routes/search_brief.py` (generate)

**Interfaces:**
- **Consumes:** `usage.reserve`, `commit`, `release`, `LimitReached`; `ai_clients.metered`.
- **Produces:**
  - `metering.start(user: User, action: str) -> str`. It converts `LimitReached` into `HTTPException(429, {"code", "action", "resets_on"})`.
  - `metering.run(reservation_id, fn, *args)`, used inside each background function. It enters `metered`, calls `fn`, commits on success and releases on any exception. Then it re-raises, so the existing error handling still records the failure.
  - **Which routes reserve:**

    | Route | Action |
    |---|---|
    | `POST job-search` | `job_search` |
    | `POST …/analyse` | `analyse`, and only when `load_analysis` misses for the job's URL key. A cached hit returns `{"status": "analysing"}`, then `ready`, without reserving |
    | `POST /api/tailor` | `tailor` |
    | `POST …/sections/{section}/draft` | `section_draft` |
    | `POST …/resume/parse` | `resume_parse` |
    | `POST …/search-brief/generate` | `search_brief` |

  - **Synchronous routes** (draft and parse) reserve, run inside `metered`, and commit or release in the same request.

- [ ] **Step 1: Write the failing tests** (fake AI clients through `ai_clients._real_*`, temporary database):
  - `test_fifth_job_search_is_429_limit_reached`
  - `test_budget_reached_429_for_everyone_including_owner`
  - `test_failed_tailor_releases_allowance`
  - `test_cached_analysis_does_not_reserve`
  - `test_each_metered_route_reserves_its_action`, parametrised over the six routes, asserting `counts_for` increases by 1 for the right action
  - `test_tailor_calls_metered_against_user_not_cli`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_limits_api.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run the same command, plus the Task 3 and Task 5 test files. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: enforce per-user allowances and the monthly ceiling on every AI action`.

### Task 7: A2A bearer token, metered as the owner

**Files:**
- Modify: `a2a/server.py`
- Create: `tests/test_a2a_auth.py`

**Interfaces:**
- **Consumes:** `usage.reserve` and the other ledger functions; `ai_clients.metered`.
- **Produces:**
  - `POST /` requires `Authorization: Bearer <A2A_TOKEN>`, compared with `hmac.compare_digest`. It returns 401 if the token is missing or wrong, and 401 for every request when `A2A_TOKEN` is unset.
  - Skill dispatch reserves against the owner's user id, or `None` if the owner hasn't signed in yet: `tailor_resume` reserves `tailor`, `job_search` reserves `job_search`, and LinkedIn reserves `cli`. A refusal comes back as a JSON-RPC error carrying the 429 detail.
  - `/.well-known/agent.json` stays public.

- [ ] **Step 1: Write the failing tests:**
  - `test_rpc_without_token_401`
  - `test_rpc_with_wrong_token_401`
  - `test_rpc_refused_when_token_unset`
  - `test_rpc_with_token_dispatches_and_reserves_owner_action`, with the skill monkeypatched
  - `test_agent_card_public`
- [ ] **Step 2:** Run `python3 -m pytest tests/test_a2a_auth.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run the same command. Expected: pass.
- [ ] **Step 5:** Commit: `feat: require a bearer token for A2A and meter it as the owner`.

### Task 8: URL safety for user-supplied job URLs

**Files:**
- Create: `core/url_safety.py`, `tests/test_url_safety.py`
- Modify: `agents/tailor_agent.py` (`fetch_job_description_with_source`, `_fetch_with_playwright`), `a2a/routes/tailor_api.py` (validate `body.url` at start)

**Interfaces:**
- **Produces:**
  - `class UnsafeURL(ValueError)`.
  - `validate_public_url(url: str) -> str`. It accepts `http` and `https` only. It resolves every address with `socket.getaddrinfo`, and rejects any address where `ipaddress.ip_address(a)` is private, loopback, link-local, reserved, multicast or unspecified.
  - `POST /api/tailor` returns 400 `{"code": "unsafe_url"}`.
  - `fetch_job_description_with_source` validates before every fetch.
  - The Playwright path installs `page.route("**/*", handler)`. The handler aborts any request, redirects included, whose URL fails `validate_public_url`.

- [ ] **Step 1: Write the failing tests** (monkeypatch `socket.getaddrinfo`):
  - `test_rejects_metadata_ip` (169.254.169.254)
  - `test_rejects_localhost_and_private_ranges` (127.0.0.1, 10.x, 192.168.x, ::1)
  - `test_rejects_hostname_resolving_to_private`
  - `test_rejects_non_http_scheme` (file://, ftp://)
  - `test_accepts_public_https`
  - `test_tailor_start_rejects_unsafe_url_400`
  - `test_playwright_route_handler_aborts_private_redirect`: unit-test the handler function with a fake route object.
- [ ] **Step 2:** Run `python3 -m pytest tests/test_url_safety.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run the same command, plus `tests/test_tailor_fit.py`. Expected: pass.
- [ ] **Step 5:** Commit: `feat: refuse job URLs that resolve to private or local addresses`.

### Task 9: Usage API

**Files:**
- Create: `a2a/routes/usage_api.py`, `tests/test_usage_api.py`
- Modify: `a2a/server.py`

**Interfaces:**
- **Consumes:** `usage.counts_for`, `summary`, `spent_this_month`, `resets_on`; `limits`.
- **Produces:** `GET /api/usage/me` returns
  `{"month", "resets_on", "paused": bool, "actions": {action: {"used": int, "limit": Optional[int]}}}`.
  - `limit` is null for the owner.
  - For the owner only, it adds `"owner": {"spent_usd", "budget_usd", "by_user": [{"email", "spent_usd", "counts"}], "by_action": {action: spent_usd}}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_usage_me_for_friend_has_limits_no_owner_block`
  - `test_usage_me_for_owner_has_spend_breakdown`
  - `test_paused_true_at_ceiling`
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement it.
- [ ] **Step 4:** Run them again. Expected: pass.
- [ ] **Step 5:** Commit: `feat: expose monthly usage and spend`.

### Task 10: Frontend sign-in gate and account menu

**Files:**
- Create: `web/components/AuthGate.tsx`, `web/components/AccountMenu.tsx`
- Modify: `web/app/layout.tsx`, `web/components/TopNav.tsx`, `web/lib/api.ts`, `web/lib/types.ts`

**Interfaces:**
- **Consumes:** `/api/auth/me`, `/api/auth/login` and `/api/auth/logout`.
- **Produces:**
  - Types: `Me` = `{email, name, picture, is_owner}`, and `ApiError extends Error` with `status: number` and `detail: unknown`. `req()` throws `ApiError`.
  - API functions: `getMe()` and `logout()`.
  - `AuthGate` wraps the layout body. It calls `getMe()`:
    - **401:** the sign-in view (`sign in` title, "sign in with google" link to `/api/auth/login`, styled as the primary button);
    - **403, or `?auth_error=not_invited`:** "this app is invite-only — ask Rohit to add {email}";
    - **`?auth_error=failed`:** "sign-in failed — try again";
    - **otherwise:** renders the children.
  - `AccountMenu` sits in TopNav: initial square, email, "usage" link, and "sign out".
  - The sign-in view is not a page, so it needs no TopNav entry.

- [ ] **Step 1:** Implement the above.
- [ ] **Step 2:** Run the typecheck. It must exit 0.
- [ ] **Step 3:** Visual check in the running app with real Google OAuth credentials that Rohit sets locally.
  - Signed out, the sign-in view shows.
  - Signing in with an invited email shows the dashboard and only your profiles.
  - Signing in with an uninvited email shows the not-invited view.
- [ ] **Step 4:** Commit: `feat(web): add sign-in gate and account menu`.

### Task 11: Usage page and limit states on metered buttons

**Files:**
- Create: `web/app/usage/page.tsx`, `web/lib/useUsage.ts`
- Modify: `web/components/TopNav.tsx` (add `usage`), `web/components/JobCard.tsx`, `web/app/jobs/page.tsx`, `web/app/tailor/page.tsx`, `web/app/search-brief/page.tsx`, `web/components/resume-edit/SectionInstructionBox.tsx`, `web/components/AddProfileModal.tsx`, `web/components/ReplaceResumeModal.tsx`

**Interfaces:**
- **Consumes:** `GET /api/usage/me`; the 429 `detail` from `ApiError`.
- **Produces:**
  - Types `UsageMe` and `UsageAction` in `types.ts`, and `getUsageMe()` in `api.ts`.
  - `useUsage()` returns `{usage, refresh, remaining(action): number | null, blockedReason(action): string | null}`. The reason is `"limit reached — resets {d Mon}"` or `"AI features paused until {d Mon}"`.
  - **Every metered button** is disabled with the reason shown next to it when `blockedReason` is non-null, and calls `refresh()` after its action. On a 429 it shows the server's reason.
  - **`/usage` page:**
    - for everyone, one row per action in the form `used X of Y · resets 1 Nov`;
    - for the owner, a stat block of `$spent of $50`, a per-user table, and spend per action.

- [ ] **Step 1:** Implement the above.
- [ ] **Step 2:** Run the typecheck. It must exit 0.
- [ ] **Step 3:** Visual check. Temporarily lower a limit through an environment override, or insert rows into a test database. Confirm that the disabled state and the `/usage` numbers match `GET /api/usage/me`.
- [ ] **Step 4:** Commit: `feat(web): add usage page and limit states on AI actions`.

### Task 12: Final verification and docs

- [ ] **Step 1:** Run `python3 -m pytest tests/ -v --ignore=tests/test_tailor.py`. Expected: all pass.
- [ ] **Step 2:** Run `cd web && npm run typecheck`. Expected: exit 0.
- [ ] **Step 3:** Run `grep -rn "anthropic.Anthropic(\|TavilyClient(" agents a2a core | grep -v core/ai_clients.py`. Expected: no output.
- [ ] **Step 4:** In the README, add a section on Google OAuth client setup: the redirect URI is `{PUBLIC_BASE_URL}/api/auth/callback`. List the environment variables and describe `scripts.assign_profile`. Use placeholders only.
- [ ] **Step 5:** End-to-end in the running app, signed in as the owner:
  - your profiles are visible;
  - one real tailor shows on `/usage`, with a non-zero measured cost;
  - a curl to `POST /` without the token returns 401.
