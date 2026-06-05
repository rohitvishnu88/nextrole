import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
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


@router.get("/{slug}/search-brief")
def get_search_brief(slug: str):
    return _load_brief(slug)


def _run_generation(slug: str) -> None:
    """Background task — calls Claude and writes the brief file when done."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
    from config import extract_json_object
    import anthropic

    resume_file = _resume_file(slug)
    if not resume_file.exists():
        return

    resume = json.loads(resume_file.read_text(encoding="utf-8"))

    prompt = f"""You are analysing a resume to generate a structured job-search brief.

Return a JSON object with exactly this structure:
{{
  "headline": "one sentence describing the candidate and what they are targeting",
  "signals": [
    {{
      "id": "<8-char hex>",
      "category": "<one of: roles|skills|location|seniority|industries|exclusions>",
      "label": "<short label, 1-5 words>",
      "confidence": "<high|medium|low>",
      "source": "<5-8 words: where this came from in the resume>",
      "active": true
    }}
  ]
}}

Confidence rules:
- high: directly stated (job title, explicitly listed skill, stated location or work rights)
- medium: inferred from context (employer names -> industry, closely related tech)
- low: reasonable default assumption

Generate signals for ALL six categories:
- roles: 4-8 target job titles the agent should search for (based on experience + titles)
- skills: 6-12 core technical skills/tools to include in search queries
- location: 2-4 location signals (derived from current location + work rights field)
- seniority: 1-2 signals for target seniority level (what to INCLUDE)
- industries: 2-5 industry preferences (from employer / client history)
- exclusions: 3-6 things to NEVER match (junior titles, wrong locations, unrelated domains)

For IDs use random 8-char hex strings.
Return ONLY the JSON object, no other text.

RESUME:
{json.dumps(resume, indent=2)[:5000]}"""

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
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


@router.post("/{slug}/search-brief/generate")
def generate_search_brief(slug: str, background_tasks: BackgroundTasks):
    resume_file = _resume_file(slug)
    if not resume_file.exists():
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    # Delete old brief so GET returns 404 while generating
    brief_f = _brief_file(slug)
    if brief_f.exists():
        brief_f.unlink()

    background_tasks.add_task(_run_generation, slug)
    return {"status": "generating"}

    _save_brief(slug, brief)
    return brief


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


@router.delete("/{slug}/search-brief/signals/{signal_id}")
def delete_signal(slug: str, signal_id: str):
    brief = _load_brief(slug)
    original_len = len(brief["signals"])
    brief["signals"] = [s for s in brief["signals"] if s["id"] != signal_id]
    if len(brief["signals"]) == original_len:
        raise HTTPException(status_code=404, detail="Signal not found")
    _save_brief(slug, brief)
    return {"deleted": signal_id}
