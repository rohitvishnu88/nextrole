# Search Brief — Signal Strength Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate a per-profile "search brief" from the resume using Claude, expose it via API, and display it in the UI as an interactive Signal Strength Board — chips grouped by category with confidence indicators, source tooltips, active toggles, and a live query preview panel.

**Architecture:** Claude reads a profile's `resume_data.json` and returns a structured JSON array of "signals" (role titles, skills, location, seniority, industries, exclusions) each with a confidence level (high/medium/low) and a human-readable source explanation. The brief is stored at `data/profiles/{slug}/search_brief.json`. Three API routes handle generate / get / patch. The job search agent reads the brief instead of hardcoded strings. The frontend Signal Strength Board page renders chips per category, with a right-side panel that constructs and updates live Tavily-style query previews as signals are toggled.

**Tech Stack:** Python (FastAPI, anthropic SDK), Next.js 14 (React, TypeScript, Tailwind), existing `core/config.py` constants, existing `@dnd-kit` already installed (not needed here), `lucide-react` for icons.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| CREATE | `a2a/routes/search_brief.py` | Generate, get, and patch search brief endpoints |
| MODIFY | `a2a/server.py` | Mount new search_brief router |
| MODIFY | `agents/job_search_agent.py` | `build_profile_summary()` reads from brief file instead of hardcoded strings |
| MODIFY | `web/lib/types.ts` | Add `Signal`, `SearchBrief` interfaces |
| MODIFY | `web/lib/api.ts` | Add `getSearchBrief`, `generateSearchBrief`, `patchSignal` functions |
| CREATE | `web/components/SignalChip.tsx` | Single chip: label + confidence dot + tooltip + toggle |
| CREATE | `web/components/QueryPreview.tsx` | Right panel — constructs and displays live query strings |
| CREATE | `web/app/search-brief/page.tsx` | The full Signal Strength Board page |
| MODIFY | `web/components/TopNav.tsx` | Add "Search Brief" nav item |
| CREATE | `tests/test_search_brief_api.py` | Tests for generate/get/patch endpoints |

---

## Data Structures

### `data/profiles/{slug}/search_brief.json`

```json
{
  "generated_at": "2026-05-31T10:00:00+00:00",
  "headline": "15 years data & integration engineering — targeting architect roles in the UK",
  "signals": [
    {
      "id": "a1b2c3d4",
      "category": "roles",
      "label": "Data Integration Architect",
      "confidence": "high",
      "source": "Current job title at WBBS",
      "active": true
    },
    {
      "id": "b2c3d4e5",
      "category": "skills",
      "label": "MuleSoft",
      "confidence": "high",
      "source": "Listed in Integration & API skills, found in 5 experience bullets",
      "active": true
    },
    {
      "id": "c3d4e5f6",
      "category": "location",
      "label": "Remote UK",
      "confidence": "high",
      "source": "Work rights field: ILR applied",
      "active": true
    },
    {
      "id": "d4e5f6g7",
      "category": "seniority",
      "label": "Architect / Principal",
      "confidence": "high",
      "source": "15+ years experience, all recent titles are architect-level",
      "active": true
    },
    {
      "id": "e5f6g7h8",
      "category": "industries",
      "label": "Financial Services",
      "confidence": "medium",
      "source": "Inferred from WBBS and Deloitte client work",
      "active": true
    },
    {
      "id": "f6g7h8i9",
      "category": "exclusions",
      "label": "Junior / Graduate",
      "confidence": "high",
      "source": "Seniority level — these should never match",
      "active": true
    }
  ]
}
```

**Confidence levels:**
- `high` — directly stated in the resume (job title, explicitly listed skill, location)
- `medium` — inferred from context (industry from employer names, transferable tech)
- `low` — reasonable assumption (e.g. open to permanent or contract)

**Categories:** `roles` | `skills` | `location` | `seniority` | `industries` | `exclusions`

---

### Task 1: Create `a2a/routes/search_brief.py` with TDD

**Files:**
- Create: `a2a/routes/search_brief.py`
- Create: `tests/test_search_brief_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_search_brief_api.py
import sys, json, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILES_DIR", str(tmp_path / "profiles"))
    # Create a minimal profile + resume
    p_dir = tmp_path / "profiles" / "test-user"
    p_dir.mkdir(parents=True)
    resume = {
        "name": "Test User",
        "summary": "Senior data engineer with 10 years experience.",
        "experience": [
            {"title": "Data Engineer", "company": "Acme", "description": ["Built pipelines"]}
        ],
        "skills": {"Cloud": ["AWS", "GCP"]},
        "education": [],
        "certifications": [],
        "work_right": "UK citizen",
    }
    (p_dir / "resume_data.json").write_text(json.dumps(resume))
    return tmp_path / "profiles"


@pytest.fixture
def client(profiles_dir):
    import importlib
    import a2a.routes.search_brief as mod
    importlib.reload(mod)
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def test_get_brief_404_when_not_generated(client):
    resp = client.get("/api/profiles/test-user/search-brief")
    assert resp.status_code == 404


def test_get_brief_returns_saved_brief(client, profiles_dir):
    brief = {
        "generated_at": "2026-05-31T00:00:00",
        "headline": "Test headline",
        "signals": [
            {"id": "abc", "category": "roles", "label": "Data Engineer",
             "confidence": "high", "source": "Job title", "active": True}
        ]
    }
    (profiles_dir / "test-user" / "search_brief.json").write_text(json.dumps(brief))
    resp = client.get("/api/profiles/test-user/search-brief")
    assert resp.status_code == 200
    assert resp.json()["headline"] == "Test headline"
    assert len(resp.json()["signals"]) == 1


def test_patch_signal_toggles_active(client, profiles_dir):
    brief = {
        "generated_at": "2026-05-31T00:00:00",
        "headline": "Test",
        "signals": [
            {"id": "abc", "category": "roles", "label": "Data Engineer",
             "confidence": "high", "source": "Job title", "active": True}
        ]
    }
    (profiles_dir / "test-user" / "search_brief.json").write_text(json.dumps(brief))
    resp = client.patch("/api/profiles/test-user/search-brief/signals/abc", json={"active": False})
    assert resp.status_code == 200
    updated = client.get("/api/profiles/test-user/search-brief").json()
    assert updated["signals"][0]["active"] is False


def test_patch_signal_404_unknown_id(client, profiles_dir):
    brief = {"generated_at": "2026-05-31", "headline": "T", "signals": []}
    (profiles_dir / "test-user" / "search_brief.json").write_text(json.dumps(brief))
    resp = client.patch("/api/profiles/test-user/search-brief/signals/nonexistent", json={"active": False})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/rohit/resume-builder
python3 -m pytest tests/test_search_brief_api.py -v 2>&1 | head -15
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create `a2a/routes/search_brief.py`**

```python
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/profiles", tags=["search-brief"])

CATEGORIES = ("roles", "skills", "location", "seniority", "industries", "exclusions")


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR",
                          str(Path(__file__).parent.parent.parent / "data" / "profiles"))
    return Path(base)


def _brief_file(slug: str) -> Path:
    return _profiles_dir() / slug / "search_brief.json"


def _resume_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_data.json"


def _load_brief(slug: str) -> dict:
    f = _brief_file(slug)
    if not f.exists():
        raise HTTPException(status_code=404, detail="Search brief not generated yet")
    return json.loads(f.read_text(encoding="utf-8"))


def _save_brief(slug: str, brief: dict) -> None:
    _brief_file(slug).write_text(json.dumps(brief, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# GET /api/profiles/{slug}/search-brief
# ---------------------------------------------------------------------------

@router.get("/{slug}/search-brief")
def get_search_brief(slug: str):
    return _load_brief(slug)


# ---------------------------------------------------------------------------
# POST /api/profiles/{slug}/search-brief/generate
# ---------------------------------------------------------------------------

@router.post("/{slug}/search-brief/generate")
def generate_search_brief(slug: str):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
    from config import MODEL, extract_json_object
    import anthropic

    resume_file = _resume_file(slug)
    if not resume_file.exists():
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    resume = json.loads(resume_file.read_text(encoding="utf-8"))

    prompt = f"""You are analysing a resume to generate a structured job-search brief.

Return a JSON object with exactly this structure:
{{
  "headline": "one sentence describing the candidate and what they're targeting",
  "signals": [
    {{
      "id": "<8-char hex>",
      "category": "<one of: roles|skills|location|seniority|industries|exclusions>",
      "label": "<short label, 1-5 words>",
      "confidence": "<high|medium|low>",
      "source": "<one sentence explaining why this was inferred from the resume>",
      "active": true
    }}
  ]
}}

Confidence rules:
- high: directly stated (job title, explicitly listed skill, stated location or work rights)
- medium: inferred from context (employer names → industry, closely related tech)
- low: reasonable default assumption

Generate signals for ALL six categories:
- roles: 4-8 target job titles the agent should search for (based on experience + titles)
- skills: 6-12 core technical skills/tools to include in search queries
- location: 2-4 location signals (derived from current location + work rights)
- seniority: 1-2 signals for target seniority level (what to INCLUDE)
- industries: 2-5 industry preferences (from employer / client history)
- exclusions: 3-6 things to NEVER match (junior titles, wrong locations, unrelated domains)

For IDs use random 8-char hex strings.
Return ONLY the JSON object, no other text.

RESUME:
{json.dumps(resume, indent=2)[:5000]}"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    result = json.loads(extract_json_object(response.content[0].text))

    brief = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline": result.get("headline", ""),
        "signals": result.get("signals", []),
    }

    _save_brief(slug, brief)
    return brief


# ---------------------------------------------------------------------------
# PATCH /api/profiles/{slug}/search-brief/signals/{signal_id}
# ---------------------------------------------------------------------------

class SignalPatch(BaseModel):
    active: Optional[bool] = None
    label: Optional[str] = None


@router.patch("/{slug}/search-brief/signals/{signal_id}")
def patch_signal(slug: str, signal_id: str, body: SignalPatch):
    brief = _load_brief(slug)
    signal = next((s for s in brief["signals"] if s["id"] == signal_id), None)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    if body.active is not None:
        signal["active"] = body.active
    if body.label is not None:
        signal["label"] = body.label
    _save_brief(slug, brief)
    return signal


# ---------------------------------------------------------------------------
# POST /api/profiles/{slug}/search-brief/signals  (add a signal manually)
# ---------------------------------------------------------------------------

class SignalCreate(BaseModel):
    category: str
    label: str
    confidence: str = "low"
    source: str = "Manually added"
    active: bool = True


@router.post("/{slug}/search-brief/signals")
def add_signal(slug: str, body: SignalCreate):
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of: {CATEGORIES}")
    brief = _load_brief(slug)
    signal = {
        "id": uuid.uuid4().hex[:8],
        "category": body.category,
        "label": body.label,
        "confidence": body.confidence,
        "source": body.source,
        "active": body.active,
    }
    brief["signals"].append(signal)
    _save_brief(slug, brief)
    return signal


# ---------------------------------------------------------------------------
# DELETE /api/profiles/{slug}/search-brief/signals/{signal_id}
# ---------------------------------------------------------------------------

@router.delete("/{slug}/search-brief/signals/{signal_id}")
def delete_signal(slug: str, signal_id: str):
    brief = _load_brief(slug)
    original_len = len(brief["signals"])
    brief["signals"] = [s for s in brief["signals"] if s["id"] != signal_id]
    if len(brief["signals"]) == original_len:
        raise HTTPException(status_code=404, detail="Signal not found")
    _save_brief(slug, brief)
    return {"deleted": signal_id}
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_search_brief_api.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add a2a/routes/search_brief.py tests/test_search_brief_api.py
git commit -m "feat: add search brief API — generate, get, patch signals"
```

---

### Task 2: Mount router and update job_search_agent

**Files:**
- Modify: `a2a/server.py`
- Modify: `agents/job_search_agent.py`

- [ ] **Step 1: Mount the router in `a2a/server.py`**

After the existing `from .routes import profiles, applications, tailor_api` line, add:
```python
from .routes import search_brief
```

After the existing `app.include_router(tailor_api.router)` line, add:
```python
app.include_router(search_brief.router)
```

- [ ] **Step 2: Update `build_profile_summary()` in `agents/job_search_agent.py`**

Replace the entire `build_profile_summary` function with this version that reads from the search brief when available, falling back to the current hardcoded approach when no brief exists:

```python
def build_profile_summary(resume: dict, profile_slug: str = "") -> str:
    """Build the Claude system prompt for job search.
    
    When a search brief exists for the profile, uses its signals instead of
    hardcoded strings so each profile gets tailored search parameters.
    """
    name = resume.get("name", "")
    summary = resume.get("summary", "")

    # Try to load signals from search brief
    brief_path = ROOT / "data" / "profiles" / profile_slug / "search_brief.json" if profile_slug else None
    if brief_path and brief_path.exists():
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        signals = [s for s in brief.get("signals", []) if s.get("active")]

        def sig(cat: str) -> list[str]:
            return [s["label"] for s in signals if s["category"] == cat]

        roles      = sig("roles")
        skills     = sig("skills")
        locations  = sig("location")
        industries = sig("industries")
        excludes   = sig("exclusions")
        seniority  = sig("seniority")

        skills_section = "\n".join(
            f'  {group}: {", ".join(items)}'
            for group, items in resume.get("skills", {}).items()
        )

        return f"""Candidate: {name}
Seniority target: {", ".join(seniority) if seniority else "Senior/Principal"}
Current role: {resume.get("experience", [{}])[0].get("title", "")} at {resume.get("experience", [{}])[0].get("company", "")}
Summary: {summary}

Target roles (search for any of these): {", ".join(roles) if roles else "Solution Architect, Senior Data Engineer"}

Core skills to match:
{chr(10).join(f"  - {s}" for s in skills) if skills else skills_section}

Target locations: {", ".join(locations) if locations else "UK only"}
Target industries: {", ".join(industries) if industries else "any industry"}

Hard exclusions (never match):
{chr(10).join(f"  - {e}" for e in excludes) if excludes else "  - Junior, Graduate, Associate, Entry-level"}

Additional context:
{skills_section}

Hard requirements:
- Posted within the last 5 days. Discard anything older.
- LinkedIn jobs only."""

    # Fallback: original hardcoded profile (unchanged from before)
    titles = [exp.get("title", "") for exp in resume.get("experience", [])[:3]]
    companies = [exp.get("company", "") for exp in resume.get("experience", [])[:3]]
    skills_by_group = resume.get("skills", {})
    all_skills = []
    for group in skills_by_group.values():
        all_skills.extend(group)
    certs = [c.get("name", "") for c in resume.get("certifications", [])]

    return f"""Candidate: {name}
Seniority: Senior/Principal level, 15 years total experience
Current role: {titles[0] if titles else ''} at {companies[0] if companies else ''}
Recent titles: {', '.join(titles)}
Summary: {summary}

Target roles (any of these): Solution Architect, Integration Architect, API Architect, Data Integration Architect, Data Architect, Data Platform Architect, Technical Architect, Enterprise Architect, Senior Data Engineer, Lead Data Engineer, Staff Data Engineer, Principal Data Engineer, Data Platform Engineer, Head of Data Engineering, Engineering Manager (Data/Integration)

Transferable tech (candidate can cover these without significant learning — include roles using these):
- Databricks / Delta Lake (same as PySpark + Iceberg — direct transfer)
- Azure Data Factory, Synapse Analytics (same patterns as AWS Glue + MWAA)
- Azure Event Hubs (same as Kafka)
- dbt (same SQL transformation layer, candidate uses PySpark equivalents)
- Snowflake (certified Snowflake Pro Core)
- Azure API Management, AWS API Gateway (same as Apigee/Kong/MuleSoft)
- IBM App Connect, WSO2, Boomi (same as MuleSoft integration patterns)

Target industries: Financial services, Banking, Automotive, Aviation, Telecoms, Retail — or open to any industry

Location: UK only (London, remote-UK, hybrid-UK). No relocation.

Core skills:
{chr(10).join(f'  {group}: {", ".join(items)}' for group, items in skills_by_group.items())}

Certifications: {', '.join(certs)}

Hard requirements for a job to be relevant:
- Senior/Lead/Principal/Architect level only. No junior, mid-level, graduate, or associate roles.
- UK-based or remote-UK. No international relocation.
- Must involve at least 2 of: data engineering, cloud data platforms, API/integration architecture, solution architecture
- Permanent or contract — either fine
- Posted within the last 5 days. Discard anything older."""
```

- [ ] **Step 3: Update the `run()` call to `build_profile_summary` in `job_search_agent.py`**

Find the line in `run()` that calls `build_profile_summary`:
```python
    profile = build_profile_summary(resume)
```

The `run()` function signature is `def run(resume: dict, include_seen: bool = False)`. Add `profile_slug: str = ""` as a third parameter:
```python
def run(resume: dict, include_seen: bool = False, profile_slug: str = "") -> dict:
```

Update the call inside `run()`:
```python
    profile = build_profile_summary(resume, profile_slug)
```

- [ ] **Step 4: Update `main_agent.py` to pass profile_slug to job_search_agent**

In `agents/main_agent.py`, find the line:
```python
        jobs_result = job_search_agent.run(resume, include_seen=args.include_seen)
```

Replace with:
```python
        jobs_result = job_search_agent.run(resume, include_seen=args.include_seen, profile_slug=profile_slug)
```

- [ ] **Step 5: Smoke test**

```bash
cd /Users/rohit/resume-builder
python3 -c "
import sys; sys.path.insert(0, 'agents')
import job_search_agent, inspect
sig = inspect.signature(job_search_agent.run)
print('run signature:', sig)
assert 'profile_slug' in sig.parameters
sig2 = inspect.signature(job_search_agent.build_profile_summary)
assert 'profile_slug' in sig2.parameters
print('OK')
"
```

Expected: Both signatures include `profile_slug`.

- [ ] **Step 6: Verify server starts with new route**

```bash
python3 -m uvicorn a2a.server:app --port 8000 --timeout-keep-alive 1 &
sleep 3
curl -s http://localhost:8000/api/profiles/rohit/search-brief | head -c 100
kill %1
```

Expected: `{"detail":"Search brief not generated yet"}` (404, which is correct — not generated yet).

- [ ] **Step 7: Commit**

```bash
git add a2a/server.py agents/job_search_agent.py agents/main_agent.py
git commit -m "feat: mount search-brief router; job_search_agent reads signals from brief"
```

---

### Task 3: TypeScript types and API client additions

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`

- [ ] **Step 1: Add types to `web/lib/types.ts`**

Append to the end of the file:

```typescript
export type SignalConfidence = "high" | "medium" | "low";
export type SignalCategory =
  | "roles"
  | "skills"
  | "location"
  | "seniority"
  | "industries"
  | "exclusions";

export interface Signal {
  id: string;
  category: SignalCategory;
  label: string;
  confidence: SignalConfidence;
  source: string;
  active: boolean;
}

export interface SearchBrief {
  generated_at: string;
  headline: string;
  signals: Signal[];
}
```

- [ ] **Step 2: Add API functions to `web/lib/api.ts`**

Append to the end of the file:

```typescript
// Search Brief
export const getSearchBrief = (slug: string) =>
  req<SearchBrief>(`/profiles/${slug}/search-brief`);

export const generateSearchBrief = (slug: string) =>
  req<SearchBrief>(`/profiles/${slug}/search-brief/generate`, { method: "POST" });

export const patchSignal = (
  slug: string,
  signalId: string,
  patch: { active?: boolean; label?: string }
) =>
  req<Signal>(`/profiles/${slug}/search-brief/signals/${signalId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

export const addSignal = (
  slug: string,
  data: { category: string; label: string }
) =>
  req<Signal>(`/profiles/${slug}/search-brief/signals`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const deleteSignal = (slug: string, signalId: string) =>
  req<{ deleted: string }>(`/profiles/${slug}/search-brief/signals/${signalId}`, {
    method: "DELETE",
  });
```

Add the import to the top of `web/lib/api.ts` (update the existing import line):
```typescript
import type { Application, ApplicationStatus, Profile, TailorJob, SearchBrief, Signal } from "./types";
```

- [ ] **Step 3: Typecheck**

```bash
cd /Users/rohit/resume-builder/web && npm run typecheck
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/lib/types.ts web/lib/api.ts
git commit -m "feat: add SearchBrief/Signal types and API client functions"
```

---

### Task 4: `SignalChip` component

**Files:**
- Create: `web/components/SignalChip.tsx`

- [ ] **Step 1: Create `web/components/SignalChip.tsx`**

```tsx
"use client";
import { useState } from "react";
import { X, Info } from "lucide-react";
import type { Signal, SignalConfidence } from "@/lib/types";

const CONFIDENCE_DOT: Record<SignalConfidence, string> = {
  high:   "bg-green-500",
  medium: "bg-yellow-400",
  low:    "bg-gray-300",
};

const CONFIDENCE_BG: Record<SignalConfidence, string> = {
  high:   "bg-green-soft border-green-200",
  medium: "bg-yellow-50 border-yellow-100",
  low:    "bg-cream border-warm-border",
};

const CONFIDENCE_LABEL: Record<SignalConfidence, string> = {
  high:   "Directly in resume",
  medium: "Inferred",
  low:    "Default assumption",
};

interface Props {
  signal: Signal;
  onToggle: (id: string, active: boolean) => void;
  onDelete: (id: string) => void;
}

export function SignalChip({ signal, onToggle, onDelete }: Props) {
  const [showTooltip, setShowTooltip] = useState(false);

  const bg = signal.active ? CONFIDENCE_BG[signal.confidence] : "bg-gray-50 border-gray-200";
  const textColor = signal.active ? "text-navy" : "text-muted line-through";

  return (
    <div className={`relative inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium transition-all ${bg}`}>
      {/* Confidence dot */}
      <span
        className={`w-2 h-2 rounded-full shrink-0 transition-colors ${
          signal.active ? CONFIDENCE_DOT[signal.confidence] : "bg-gray-300"
        }`}
      />

      {/* Label */}
      <span className={`transition-colors ${textColor}`}>{signal.label}</span>

      {/* Source info icon */}
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="text-muted hover:text-navy transition-colors ml-0.5"
        aria-label="View source"
      >
        <Info size={11} />
      </button>

      {/* Toggle active */}
      <button
        onClick={() => onToggle(signal.id, !signal.active)}
        className={`w-7 h-4 rounded-full transition-colors ml-0.5 relative shrink-0 ${
          signal.active ? "bg-accent" : "bg-gray-200"
        }`}
        aria-label={signal.active ? "Disable signal" : "Enable signal"}
      >
        <span
          className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-transform ${
            signal.active ? "translate-x-3.5" : "translate-x-0.5"
          }`}
        />
      </button>

      {/* Delete */}
      <button
        onClick={() => onDelete(signal.id)}
        className="text-warm-border hover:text-red-400 transition-colors"
        aria-label="Remove signal"
      >
        <X size={11} />
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 pointer-events-none">
          <div className="bg-navy text-white text-xs rounded-xl px-3 py-2 w-52 shadow-lg">
            <p className="font-semibold mb-0.5">
              {CONFIDENCE_LABEL[signal.confidence]}
            </p>
            <p className="text-white/80 leading-relaxed">{signal.source}</p>
          </div>
          <div className="w-2 h-2 bg-navy rotate-45 mx-auto -mt-1" />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd /Users/rohit/resume-builder/web && npm run typecheck
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/components/SignalChip.tsx
git commit -m "feat: add SignalChip component with confidence dot, toggle, tooltip, delete"
```

---

### Task 5: `QueryPreview` component

**Files:**
- Create: `web/components/QueryPreview.tsx`

- [ ] **Step 1: Create `web/components/QueryPreview.tsx`**

```tsx
import type { Signal } from "@/lib/types";

interface Props {
  signals: Signal[];
}

function buildQueries(signals: Signal[]): string[] {
  const active = signals.filter(s => s.active);

  const roles     = active.filter(s => s.category === "roles").map(s => s.label).slice(0, 4);
  const skills    = active.filter(s => s.category === "skills").map(s => s.label).slice(0, 3);
  const locations = active.filter(s => s.category === "location").map(s => s.label).slice(0, 2);

  if (roles.length === 0) return ["No active role signals — enable at least one role."];

  const loc = locations.length > 0 ? locations[0] : "UK";
  const skill1 = skills[0] ?? "";
  const skill2 = skills[1] ?? "";

  const queries: string[] = [];

  // Direct listing queries (role + skill + location)
  if (roles[0]) {
    queries.push(
      `site:linkedin.com/jobs/view "${roles[0]}" ${skill1} ${loc}`.trim()
    );
  }
  if (roles[1]) {
    queries.push(
      `site:linkedin.com/jobs/view "${roles[1]}" ${skill2} ${loc}`.trim()
    );
  }

  // Search page queries
  if (roles[0]) {
    queries.push(
      `site:linkedin.com/jobs/search keywords="${roles[0]}" location=${loc} f_TPR=r432000`
    );
  }
  if (roles[2]) {
    queries.push(
      `site:linkedin.com/jobs/view "${roles[2]}" ${skill1} ${loc} f_TPR=r432000`.trim()
    );
  }

  // Skill-angle query
  if (skill1 && roles[0]) {
    queries.push(
      `site:linkedin.com/jobs/view ${skill1} architect ${loc}`.trim()
    );
  }

  return queries.slice(0, 5);
}

export function QueryPreview({ signals }: Props) {
  const queries = buildQueries(signals);
  const activeCount = signals.filter(s => s.active).length;

  return (
    <div className="bg-white rounded-2xl border border-warm-border p-5 sticky top-24">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-navy text-sm">Live Query Preview</h3>
        <span className="text-xs text-muted bg-cream px-2 py-0.5 rounded-full border border-warm-border">
          {activeCount} active signals
        </span>
      </div>

      <p className="text-xs text-muted mb-3 leading-relaxed">
        The job search agent constructs queries like these from your active signals.
        Toggle signals on the left to see them update.
      </p>

      <div className="space-y-2">
        {queries.map((q, i) => (
          <div key={i} className="bg-gray-950 rounded-xl px-3 py-2">
            <p className="text-green-400 text-xs font-mono leading-relaxed break-all">{q}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-warm-border">
        <div className="flex gap-3 text-xs text-muted">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
            High confidence
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
            Inferred
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-gray-300 inline-block" />
            Default
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd /Users/rohit/resume-builder/web && npm run typecheck
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/components/QueryPreview.tsx
git commit -m "feat: add QueryPreview component — live Tavily query construction from signals"
```

---

### Task 6: Search Brief page + nav link

**Files:**
- Create: `web/app/search-brief/page.tsx`
- Modify: `web/components/TopNav.tsx`

- [ ] **Step 1: Create `web/app/search-brief/page.tsx`**

```tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type { SearchBrief, Signal, SignalCategory } from "@/lib/types";
import { useActiveProfile } from "@/lib/useActiveProfile";
import { SignalChip } from "@/components/SignalChip";
import { QueryPreview } from "@/components/QueryPreview";
import { RefreshCw, Plus, Loader2 } from "lucide-react";

const CATEGORY_META: Record<SignalCategory, { label: string; description: string }> = {
  roles:      { label: "Target Roles",   description: "Job titles the agent actively searches for" },
  skills:     { label: "Core Skills",    description: "Technologies used in search queries" },
  location:   { label: "Location",       description: "Where to search — derived from work rights" },
  seniority:  { label: "Seniority",      description: "Career level to target" },
  industries: { label: "Industries",     description: "Preferred sectors (informational — not a hard filter)" },
  exclusions: { label: "Exclusions",     description: "Terms that disqualify a job immediately" },
};

const CATEGORY_ORDER: SignalCategory[] = [
  "roles", "skills", "location", "seniority", "industries", "exclusions",
];

export default function SearchBriefPage() {
  const profile = useActiveProfile();
  const [brief, setBrief] = useState<SearchBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [addingCategory, setAddingCategory] = useState<SignalCategory | null>(null);
  const [newLabel, setNewLabel] = useState("");

  const load = useCallback(async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const data = await api.getSearchBrief(profile);
      setBrief(data);
    } catch {
      setBrief(null);
    } finally {
      setLoading(false);
    }
  }, [profile]);

  useEffect(() => { load(); }, [load]);

  async function handleGenerate() {
    if (!profile) return;
    setGenerating(true);
    setError("");
    try {
      const data = await api.generateSearchBrief(profile);
      setBrief(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate");
    } finally {
      setGenerating(false);
    }
  }

  async function handleToggle(id: string, active: boolean) {
    if (!profile || !brief) return;
    const updated = await api.patchSignal(profile, id, { active });
    setBrief(b => b ? {
      ...b,
      signals: b.signals.map(s => s.id === id ? { ...s, ...updated } : s),
    } : b);
  }

  async function handleDelete(id: string) {
    if (!profile || !brief) return;
    await api.deleteSignal(profile, id);
    setBrief(b => b ? { ...b, signals: b.signals.filter(s => s.id !== id) } : b);
  }

  async function handleAdd(category: SignalCategory) {
    if (!profile || !newLabel.trim()) return;
    const signal = await api.addSignal(profile, { category, label: newLabel.trim() });
    setBrief(b => b ? { ...b, signals: [...b.signals, signal] } : b);
    setNewLabel("");
    setAddingCategory(null);
  }

  const signalsByCategory = (cat: SignalCategory): Signal[] =>
    (brief?.signals ?? []).filter(s => s.category === cat);

  if (!profile) {
    return (
      <div className="bg-yellow-50 border border-yellow-100 rounded-2xl px-5 py-4 text-sm text-yellow-700">
        Select a profile first.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Search Brief</h1>
          <p className="text-sm text-muted mt-1">
            {brief
              ? brief.headline
              : "Generate a brief to see what parameters the job search agent uses"}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-white rounded-xl px-4 py-2 text-sm font-semibold transition-colors shrink-0"
        >
          {generating
            ? <Loader2 size={14} className="animate-spin" />
            : <RefreshCw size={14} />}
          {brief ? "Regenerate" : "Generate from Resume"}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 rounded-2xl px-5 py-3 text-sm text-red-600">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-muted text-sm py-4">
          <Loader2 size={14} className="animate-spin" />
          Loading brief…
        </div>
      )}

      {!loading && !brief && !generating && (
        <div className="bg-white rounded-2xl border border-warm-border p-12 text-center">
          <p className="text-navy font-medium mb-1">No search brief yet</p>
          <p className="text-muted text-sm">
            Click "Generate from Resume" — Claude will read your resume and extract
            the search parameters automatically.
          </p>
        </div>
      )}

      {brief && (
        <div className="grid grid-cols-3 gap-6 items-start">

          {/* Signal categories — 2 cols */}
          <div className="col-span-2 space-y-5">
            {CATEGORY_ORDER.map(cat => {
              const meta = CATEGORY_META[cat];
              const chips = signalsByCategory(cat);

              return (
                <div key={cat} className="bg-white rounded-2xl border border-warm-border p-5">
                  <div className="flex items-baseline justify-between mb-1">
                    <h2 className="font-semibold text-navy text-sm">{meta.label}</h2>
                    <span className="text-xs text-muted">{chips.filter(s => s.active).length}/{chips.length} active</span>
                  </div>
                  <p className="text-xs text-muted mb-3">{meta.description}</p>

                  <div className="flex flex-wrap gap-2">
                    {chips.map(signal => (
                      <SignalChip
                        key={signal.id}
                        signal={signal}
                        onToggle={handleToggle}
                        onDelete={handleDelete}
                      />
                    ))}

                    {/* Add signal inline */}
                    {addingCategory === cat ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          autoFocus
                          value={newLabel}
                          onChange={e => setNewLabel(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === "Enter") handleAdd(cat);
                            if (e.key === "Escape") { setAddingCategory(null); setNewLabel(""); }
                          }}
                          placeholder="Label…"
                          className="text-sm border border-warm-border rounded-xl px-3 py-1.5 text-navy placeholder-muted bg-cream focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent w-36"
                        />
                        <button
                          onClick={() => handleAdd(cat)}
                          className="text-xs bg-accent text-white rounded-xl px-3 py-1.5 font-medium hover:bg-accent-hover transition-colors"
                        >
                          Add
                        </button>
                        <button
                          onClick={() => { setAddingCategory(null); setNewLabel(""); }}
                          className="text-xs text-muted hover:text-navy transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setAddingCategory(cat)}
                        className="flex items-center gap-1 text-xs text-muted hover:text-accent border border-dashed border-warm-border rounded-full px-3 py-1.5 transition-colors"
                      >
                        <Plus size={11} />
                        Add
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Query preview — 1 col sticky */}
          <div className="col-span-1">
            <QueryPreview signals={brief.signals} />
          </div>

        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add "Search Brief" to `web/components/TopNav.tsx`**

Add `Search` icon to the import:
```tsx
import { LayoutDashboard, FileText, Briefcase, Search } from "lucide-react";
```

Add to the `nav` array:
```tsx
const nav = [
  { href: "/",              label: "Dashboard",    icon: LayoutDashboard },
  { href: "/tailor",        label: "Tailor Resume", icon: FileText },
  { href: "/applications",  label: "Applications",  icon: Briefcase },
  { href: "/search-brief",  label: "Search Brief",  icon: Search },
];
```

- [ ] **Step 3: Typecheck**

```bash
cd /Users/rohit/resume-builder/web && npm run typecheck
```

Expected: No errors.

- [ ] **Step 4: Restart FastAPI and smoke test the full flow**

```bash
# Terminal 1
python3 -m uvicorn a2a.server:app --port 8000 --reload

# Terminal 2
cd /Users/rohit/resume-builder/web && npm run dev
```

Open `http://localhost:3000/search-brief`:
1. Select the "Rohit" profile
2. Click "Generate from Resume" — expect ~10s for Claude to respond
3. Signals appear grouped by category with confidence dots
4. Toggle a signal — query preview updates on the right
5. Hover the info icon on a chip — tooltip shows source text
6. Click "+ Add" in a category — inline input appears
7. Type a label, press Enter — new chip with grey confidence dot appears

- [ ] **Step 5: Commit**

```bash
cd /Users/rohit/resume-builder
git add web/app/search-brief/ web/components/TopNav.tsx
git commit -m "feat: add Search Brief page — signal board with confidence chips and live query preview"
```

---

## Verification Checklist

After all tasks:

- [ ] `python3 -m pytest tests/test_search_brief_api.py -v` — 4 tests pass
- [ ] `cd web && npm run typecheck` — no errors
- [ ] `GET /api/profiles/rohit/search-brief` → 404 before generation, 200 after
- [ ] `POST /api/profiles/rohit/search-brief/generate` → returns brief JSON with 6 categories of signals
- [ ] `PATCH /api/profiles/rohit/search-brief/signals/{id}` → toggles active, persists to file
- [ ] `/search-brief` page loads, generates brief, chips render with correct colours
- [ ] Toggling a chip updates query preview in real-time
- [ ] Hover info icon shows source tooltip
- [ ] `+ Add` inline input creates a new grey (low confidence) chip
- [ ] `X` on chip deletes it, immediately removed from UI
