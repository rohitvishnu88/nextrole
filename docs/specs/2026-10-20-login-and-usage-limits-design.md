# Login and usage limits: design

Date: 2026-10-20
Status: approved 2026-10-20

## Intent

Rohit wants about five friends to use the app as their own small job-search portal. Each friend uploads their resume, searches for jobs, and tailors resumes for themselves. Today the app has no users: everyone sees every profile, and every AI call runs on Rohit's Anthropic and Tavily keys with no limit.

Two things are needed:

1. **Google sign-in with private data.** Each person sees only their own profiles, applications, job matches and tailored output.
2. **Monthly usage limits.** Friends use Rohit's configured keys, so there's no setup friction for them. A per-person allowance and an overall $50 ceiling guarantee the bill.

## Goals

- Google OAuth sign-in. Only invited email addresses can get in.
- All data scoped to the signed-in user. Nobody can read or change another person's data through any route.
- Every action that calls Claude or Tavily is metered and limited per user per calendar month.
- A hard ceiling of **$50 of measured spend per calendar month across everyone, including Rohit**. When it's reached, all AI features pause until the 1st.
- Each person can see their remaining allowance. Rohit can also see total spend and spend per user.

## Non-goals

- Hosting or deployment. That's a separate piece of work. This design must simply be configurable through environment variables, so it can run on localhost now and on a host later.
- Bring-your-own API keys. This was considered and dropped in favour of limits (Rohit's decision).
- Payments, email and password login, other sign-in providers, and an invite UI.

## Anti-goals

- Any route, old or new, that lets one user read or change another user's data, or run an AI action without being metered.
- A friend's job matches or resume emailed to Rohit.
- Limits that block a cached or free action, such as re-opening an analysis or downloading a PDF.

## Decisions

**Rohit's:**
- Google sign-in.
- Keep A2A available, behind a token.
- Limits instead of bring-your-own-key.
- The per-friend allowances below.
- A $50 total monthly ceiling that **includes Rohit's own usage**.

**My calls, marked *(call)*, for checking:**
- *(call)* Invite-only through an email allowlist.
- *(call)* Rohit is the owner. He's exempt from per-user allowances but counts towards the $50.
- *(call)* Existing data is assigned to Rohit's account.
- *(call)* Job-search emails go only to the owner's own searches.

## Sign-in

- **Flow:** the Google OAuth 2.0 authorization-code flow, handled by the FastAPI backend using Authlib.
  - `GET /api/auth/login` redirects to Google.
  - `GET /api/auth/callback` checks the state parameter, exchanges the code, reads the verified email, and creates or updates the user.
  - `POST /api/auth/logout` signs out.
  - `GET /api/auth/me` returns `{email, name, picture, is_owner}`, or 401.
- **Session:** a signed, HttpOnly session cookie with `SameSite=Lax`, set `Secure` when served over HTTPS, lasting 30 days. The secret comes from `SESSION_SECRET`. The Next.js `/api` proxy keeps the cookie same-origin, so no CORS change is needed.
- **Invite list:**
  - `OWNER_EMAIL` and `ALLOWED_EMAILS` (comma-separated) are environment variables.
  - An email that isn't on the list, or isn't verified by Google, gets the "not invited" page. No user row is created for it.
  - Removing an email from the list blocks that person on their next request, even with an existing session.
- **Configuration:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `PUBLIC_BASE_URL` (for the redirect URI) are environment variables. They're documented in the README, never committed, and absent from example values.
- **Users table** in the existing SQLite database: `id`, `email` (unique), `name`, `picture`, `is_owner`, `created_at`, `last_login_at`.

## Data ownership

- **Profiles:** `profiles.json` entries gain `owner_user_id`. A user sees and creates only their own profiles, up to 3 per user *(call)*.
- **One check guards every route that takes a slug or ID.**
  - Profile slugs: `require_profile(slug, user)`. It covers profiles, resume, resume versions, search brief, job search, job analysis and tailor history.
  - Application IDs and tailor job IDs are checked the same way.
  - A resource that belongs to someone else returns **404, not 403**, so it doesn't reveal that it exists.
- **Applications:** created only for profiles the user owns. Listing, updating and deleting check ownership through the profile.
- **Tailor jobs:** the in-memory job record stores `user_id`. Every `/api/tailor/{job_id}/…` route checks it.
- **Every `/api` route requires a signed-in, allowed user**, except `/api/auth/*`.
- **Existing data:** profiles without an owner are assigned to the owner on first start-up. A one-off command, `python3 -m scripts.assign_profile <slug> <email>`, moves a profile to another user. This is how Malini's profile goes to her once she has signed in.
- **A2A JSON-RPC (`POST /`) stays available, protected by a bearer token** (Rohit's decision: he uses it from other tools).
  - The agent card already advertises `"schemes": ["Bearer"]`, but the server doesn't check it today.
  - `POST /` now requires `Authorization: Bearer <A2A_TOKEN>`, compared in constant time. `A2A_TOKEN` is an environment variable, never committed.
  - If `A2A_TOKEN` isn't set, `POST /` refuses every request. It fails closed.
  - A2A requests act as the owner. They're metered against him: `tailor_resume` counts as `tailor`, `job_search` as `job_search`, and LinkedIn analysis as `cli`. They're refused once the $50 ceiling is reached.
  - The agent card (`/.well-known/agent.json`) stays public. It's metadata only.
- **Job search email** is sent only when the owner runs a search, and only to the owner.

## Usage limits

**Allowance per user per calendar month (UTC):**

| Action | Limit | What it covers |
|---|---|---|
| `job_search` | 4 | One job search run |
| `tailor` | 12 | One tailoring run, including its job analysis, cover letter and humanise passes |
| `analyse` | 15 | The analyse button on a job card, when the result isn't already cached |
| `section_draft` | 20 | An AI draft in the resume editor |
| `resume_parse` | 3 | Parsing an uploaded resume (new profile or replace) |
| `search_brief` | 3 | Generating a search brief |

- **Where the limits live:** in one config module, alongside `MONTHLY_BUDGET_USD = 50`.
- **LinkedIn analysis:** has no web route and runs only through A2A or the CLI, so it gets no allowance.

**Measured spend:**
- **One wrapper for every Claude call.** All AI clients are created through a single factory that returns a metered client. There are seven construction sites today; all seven must go through it.
- **What each call records:** the usage reported in the response (input, output and cache tokens) and the model, against the current action.
- **Tavily:** calls go through a wrapper that records credits per call, using Tavily's published credit rules for search depth and extract.
- **Prices:** cost is calculated from a price table in config for each model and for each Tavily credit. Tavily credits are priced at the pay-as-you-go rate, even while on the free tier, so the ceiling stays conservative. *The builder verifies current published prices when implementing.*

**Enforcement:**
- **Reserve before starting.** Each metered action calls `reserve(user, action)` first. It's refused with HTTP 429 and a clear message when either of these is true:
  - the user's committed plus in-flight count for this action this month has reached the limit (the owner is exempt);
  - this month's total measured spend has reached `MONTHLY_BUDGET_USD`.
- **Success commits; failure releases.** A run that fails on the server's side (a crash, an unreadable ad, model output that can't be parsed) doesn't count against the user's allowance. Its measured cost still counts towards the $50, because that money was spent.
- **No reservation for cached work.** Cached analyses, downloads, viewing and editing without AI never reserve.
- **The ceiling is checked before each action, not during it.** One in-flight action can take spend slightly past $50, by at most about one job search (around $0.60). That's accepted.

**Usage table** in SQLite: `id`, `user_id`, `action`, `status` (`reserved` | `committed` | `released`), `month`, `cost_usd`, `input_tokens`, `output_tokens`, `tavily_credits`, `created_at`.

## UI (in the existing Bauhaus-lite style)

- **Sign-in page:** shown when `/api/auth/me` returns 401. It has a large lowercase title and a "sign in with google" button.
- **"Not invited" page:** says "this app is invite-only — ask Rohit to add <email>". The email shown is what Google returned.
- **Account menu in the top bar:** avatar initial, email, "usage" and "sign out". The profile switcher stays, but lists only the user's own profiles.
- **`/usage` page**, linked from TopNav as CLAUDE.md requires:
  - each action as "used X of Y · resets 1 Nov";
  - for the owner, also this month's total spend against $50, a per-user breakdown, and spend per action.
- **Every metered button** (search, tailor, analyse, draft, parse, brief):
  - shows a disabled state with "limit reached — resets 1 Nov" when the allowance is used up;
  - shows "AI features paused until 1 Nov" when the ceiling is reached;
  - the frontend reads remaining counts from `GET /api/usage/me`. The server's 429 remains the real enforcement.

## Constraints

- Python 3.9 typing, `MODEL` from `core/config.py`, and the existing background-task pattern.
- New dependencies: `authlib`, `itsdangerous` (for Starlette's `SessionMiddleware`) and `httpx`. Add them to `requirements.txt`.
- No secrets in code, tests, docs or commits.
- Tests run against real behaviour. Google's token and userinfo endpoints and the Anthropic and Tavily clients are mocked, because they're the external boundaries. Ownership is tested for every route family with two users: user B gets 404 on user A's resources. Quota tests cover the per-user limit, the global ceiling, release on failure, owner exemption, and no reservation for cached results.

## Settled after builder review (my calls; check these)

- **Hard ceiling.** `reserve()` holds an *estimated* cost for each action. The estimates are the per-action worst cases from the cost table. The ceiling check counts committed actual spend plus the estimates for actions still in flight. This keeps several users from all passing the check together just under $50. On commit, the estimate is replaced by the measured cost.
- **CLI and other non-web runs** (the `agents/*` command-line entry points): the metered factory records them against the owner as action `cli` and refuses them once the ceiling is reached. Nothing that spends money goes unmetered. The CLI needs only the local SQLite database, no sign-in.
- **Profile cap** of 3 per user: the owner is exempt, so the migration that assigns existing profiles to him can't break.
- **Server-side URL fetching is in scope.** Friends now supply URLs that the server fetches, through Tavily and the Playwright fallback. Every user-supplied job URL is validated: `http`/`https` only, and the hostname resolves to a public address (no private, loopback, link-local or metadata ranges). Redirects are re-checked for the Playwright fetch. This needs tests.

## Left to the builder

- Module layout (for example `a2a/auth.py`, `a2a/usage.py`, `core/limits.py`).
- How the metered client attaches calls to the current reservation (context variable or explicit argument).
- Page layout and copy within the redesign rules.
