# Next Role

> AI-powered job search: tailor your resume, track applications, and understand what the agent searches for.

Built with Claude AI, FastAPI, and Next.js. Runs entirely on your machine. Your data never leaves your computer.

---

## What it does

- **Resume tailoring**: paste a job URL or description, Claude rewrites your resume bullets and generates a cover letter in under a minute
- **Application tracker**: track every role from Saved to Offer in a sortable table or drag-and-drop kanban board
- **Search brief**: see exactly what parameters the job search agent uses (target roles, skills, location, seniority) and toggle signals on or off
- **Multi-profile**: upload a PDF or DOCX resume for each person; Claude parses it automatically
- **Local and private**: no cloud database, no accounts, no tracking

---

## Prerequisites

- Python 3.9+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/): required for all AI features
- A [Tavily API key](https://tavily.com/): optional, only needed for the CLI job search agent

---

## Quick start with Claude Code

If you have [Claude Code](https://claude.ai/code), setup is largely automated:

```bash
git clone <your-repo-url>
cd resume-builder
```

Open the project in Claude Code and ask:

> "Set up and run the resume builder for me."

Claude Code will read the `CLAUDE.md`, install dependencies, start both servers, and walk you through creating your first profile.

---

## Manual setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd resume-builder
```

### 2. Set your API key

**Mac / Linux**
```bash
export ANTHROPIC_API_KEY=your-key-here
# Optional: only for CLI job search
export TAVILY_API_KEY=your-key-here
```

**Windows (PowerShell)**
```powershell
$env:ANTHROPIC_API_KEY = "your-key-here"
# Optional: only for CLI job search
$env:TAVILY_API_KEY = "your-key-here"
```

### 2b. Sign-in settings

The app is invite-only and uses Google sign-in. Set these before starting the backend:

| Variable | What it is |
|---|---|
| `SESSION_SECRET` | A long random string used to sign session cookies, e.g. the output of `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | From a Google Cloud OAuth client (Web application) |
| `PUBLIC_BASE_URL` | Where the app is served, e.g. `http://localhost:3000`. Add `{PUBLIC_BASE_URL}/api/auth/callback` as an authorised redirect URI on the OAuth client |
| `OWNER_EMAIL` | Your Google email; the owner sees spend and has no per-user limits |
| `ALLOWED_EMAILS` | Comma-separated emails of invited friends |
| `A2A_TOKEN` | Shared secret for the A2A endpoint (`POST /`). Clients send `Authorization: Bearer <token>`. If unset, A2A refuses every request |

**Usage limits.** Every AI action is metered against a per-person monthly allowance and an overall $50/month ceiling (all users, including the owner). Limits and prices live in `core/limits.py`; each person sees theirs on the **usage** page, and the owner also sees spend by person.

**Giving an existing profile to a friend.** Profiles created before sign-in belong to the owner. Once the friend has signed in once:

```bash
python3 -m scripts.assign_profile <profile-slug> <their-google-email>
```

### 3. Install dependencies

**Mac / Linux**
```bash
./setup.sh
```

**Windows**
```powershell
.\setup.ps1
```

This installs Python dependencies, Playwright Chromium (for PDF generation), and Node.js dependencies.

### 4. Run the app

**Mac / Linux**
```bash
./start.sh
```

**Windows**
```powershell
.\start.ps1
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## First-time setup

1. Click your profile area (top right) and select **Add Profile**
2. Enter a name and upload your resume as a PDF or DOCX
3. Claude parses it: review the extracted data and confirm
4. Your profile is ready

---

## Usage

### Tailor a resume

1. Go to **Tailor Resume**
2. Paste a job URL or the full job description
3. Claude tailors your resume and generates a cover letter (~30–60 seconds)
4. Download the PDF and cover letter
5. Optionally add the role to your application tracker

### Track applications

Go to **Applications** to add and manage roles. Toggle between table and kanban views. Drag cards between columns (Saved → Applied → Interview → Offer → Rejected) to update status.

### Search brief

Go to **Search Brief** and click **Generate from Resume**. Claude reads your resume and extracts the parameters the job search agent uses: target roles, core skills, location, seniority, industries, and exclusions. Toggle any signal on or off and see the search queries update live on the right.

### CLI job search (optional)

The job search agent runs from the command line and requires a Tavily API key:

```bash
# Search for jobs matching your profile
python3 agents/main_agent.py --jobs-only --profile rohit

# Tailor a resume from the CLI
python3 agents/main_agent.py --tailor <linkedin-job-url> --profile rohit

# Mark a job as applied
python3 agents/main_agent.py --applied <linkedin-job-url>
```

---

## Architecture

Two processes run simultaneously:

| Process | Command | Port | Purpose |
|---|---|---|---|
| FastAPI backend | `python3 -m uvicorn a2a.server:app` | 8000 | AI operations, PDF generation, file I/O |
| Next.js frontend | `cd web && npm run dev` | 3000 | UI, proxies `/api/*` to the backend |

No special web server or database server required. SQLite handles the application tracker. Resume data is stored as JSON files in `data/profiles/`.

---

## Running on another machine

Same steps as manual setup above: clone, set API keys, run `setup` and `start`. No additional configuration needed. Each person needs their own Anthropic API key.

---

## Sharing with friends (Tailscale Funnel)

Runs the app on your Mac and publishes it at a fixed `https://<your-mac>.<tailnet>.ts.net` address. Free, no open router ports, and only the Next.js frontend is exposed (it forwards `/api` to FastAPI on localhost). The app is reachable only while your Mac is awake and `serve.sh` is running.

**1. Tailscale.** Install it (`brew install --cask tailscale` or the Mac App Store), open it and sign in. Find your address:

```bash
tailscale status --json | python3 -c "import sys, json; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))"
```

**2. Google OAuth client.** In Google Cloud Console → Credentials → your OAuth client, add the authorised redirect URI `https://<your-ts-net-address>/api/auth/callback` (keep `http://localhost:3000/api/auth/callback` for local development). On the OAuth consent screen, add each friend as a test user.

**3. Settings file**, outside the repo so secrets never reach git:

```bash
mkdir -p ~/.config/nextrole && touch ~/.config/nextrole/env && chmod 600 ~/.config/nextrole/env && open -e ~/.config/nextrole/env
```

Contents (replace every value; generate `SESSION_SECRET` once with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and keep it fixed, or everyone is signed out on restart):

```
ANTHROPIC_API_KEY=...
TAVILY_API_KEY=...
SESSION_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
OWNER_EMAIL=you@gmail.com
ALLOWED_EMAILS=friend1@gmail.com,friend2@gmail.com
PUBLIC_BASE_URL=https://<your-ts-net-address>
```

**4. Run it**, then publish port 3000 (the first `funnel` run asks you to approve Funnel in the Tailscale admin console):

```bash
./serve.sh
```

```bash
tailscale funnel --bg 3000
```

**Stop sharing:** `tailscale funnel reset`. **Keep the Mac awake** while sharing, e.g. `caffeinate -dims` in another terminal. **Back up** `data/` and `output/` regularly; they hold everyone's profiles, applications and tailored resumes. Use `./start.sh` for local development as before.

---

## Self-hosting

The app is designed for local use but can be hosted on a server. The Python backend requires a Linux environment with Chromium available for PDF generation (Railway, Fly.io, or a VPS with Docker work well). The Next.js frontend can be deployed to Vercel separately: set `NEXT_PUBLIC_API_URL` to point at your hosted backend.

---

## Tech stack

| Layer | Technology |
|---|---|
| AI | Claude Sonnet (tailoring, parsing), Claude Haiku (search brief) |
| Backend | Python 3.9, FastAPI, uvicorn, SQLite |
| PDF generation | Playwright / Chromium |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Drag and drop | dnd-kit |

---

## Project structure

```
agents/       CLI agents: tailor, job search, LinkedIn, orchestrator
a2a/          FastAPI server and REST routes
core/         Shared config, PDF renderer, Jinja2 template
data/         Profile resume data and applications database
web/          Next.js frontend
docs/         Design specs and implementation plans
tests/        pytest test suite
```

---

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | All Claude AI operations |
| `TAVILY_API_KEY` | No | CLI job search agent only |
| `NEXT_PUBLIC_API_URL` | No | Override backend URL (default: `http://localhost:8000`) |
| `CORS_ORIGINS` | No | Allowed origins for backend (default: `http://localhost:3000`) |
