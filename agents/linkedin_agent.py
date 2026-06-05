#!/usr/bin/env python3
"""
LinkedIn Profile Sub-agent
Reads your LinkedIn data export CSVs, compares against resume_data.json,
and generates optimised profile content via Claude.

Expected files in linkedin_export/:
  Profile.csv, Positions.csv, Skills.csv, Education.csv, Certifications.csv

How to export:
  LinkedIn → Settings & Privacy → Data Privacy → Get a copy of your data
  Select: Profile, Positions, Skills, Education, Certifications → Request archive
  Unzip into linkedin_export/

Note: LinkedIn export descriptions for past roles are often blank.
The agent detects this and generates suggested descriptions from your resume.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path as _Path

import anthropic

sys.path.insert(0, str(_Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL

ROOT = _Path(__file__).parent.parent
EXPORT_DIR = ROOT / "data" / "linkedin_export"
RESUME_FILE = ROOT / "data" / "resume_data.json"
OUTPUT_FILE = ROOT / "output" / "jobs" / "linkedin_updates.json"
MODEL = DEFAULT_MODEL

EXPORT_STALE_DAYS = 30


def read_csv(filename: str) -> list[dict]:
    path = Path(EXPORT_DIR) / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def export_age_days() -> "int | None":
    """Return age of the LinkedIn export in days, based on Profile.csv mtime."""
    profile_csv = EXPORT_DIR / "Profile.csv"
    if not profile_csv.exists():
        return None
    mtime = profile_csv.stat().st_mtime
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(mtime, tz=timezone.utc)
    return age.days


def load_linkedin_profile() -> dict:
    profile_rows = read_csv("Profile.csv")
    profile = profile_rows[0] if profile_rows else {}

    positions = []
    for r in read_csv("Positions.csv"):
        desc = r.get("Description", "").strip()
        positions.append({
            "title": r.get("Title", ""),
            "company": r.get("Company Name", ""),
            "start": r.get("Started On", ""),
            "end": r.get("Finished On", "Present"),
            "description": desc if desc else "[EMPTY — LinkedIn export did not include a description]",
        })

    skills = [r.get("Name", "") for r in read_csv("Skills.csv")]

    education = [
        {
            "school": r.get("School Name", ""),
            "degree": r.get("Degree Name", ""),
            "field": r.get("Field Of Study", ""),
            "start": r.get("Start Date", ""),
            "end": r.get("End Date", ""),
        }
        for r in read_csv("Education.csv")
    ]

    certifications = [
        {
            "name": r.get("Name", ""),
            "authority": r.get("Authority", ""),
        }
        for r in read_csv("Certifications.csv")
    ]

    return {
        "headline": profile.get("Headline", ""),
        "summary": profile.get("Summary", ""),
        "industry": profile.get("Industry", ""),
        "location": profile.get("Geo Location", ""),
        "positions": positions,
        "skills": skills,
        "education": education,
        "certifications": certifications,
    }


def run(resume: dict) -> dict:
    export_path = EXPORT_DIR
    has_export = export_path.exists() and any(export_path.iterdir())

    age = None
    stale_warning = None

    if has_export:
        age = export_age_days()
        if age is not None and age > EXPORT_STALE_DAYS:
            stale_warning = (
                f"LinkedIn export is {age} days old. The analysis reflects your profile "
                f"as of {age} days ago, not today. Re-export from LinkedIn for accurate results."
            )
            print(f"  ⚠️  {stale_warning}")
        elif age is not None:
            print(f"  Export age: {age} day(s) — looks fresh.")

        print("  Reading LinkedIn export...")
        linkedin = load_linkedin_profile()

        if not linkedin["headline"] and not linkedin["positions"]:
            has_export = False
            print("  ⚠️  Export files found but appear empty. Running in resume-only mode.")
        else:
            empty_desc_count = sum(
                1 for p in linkedin["positions"]
                if "[EMPTY" in p.get("description", "")
            )
            if empty_desc_count:
                print(
                    f"  ⚠️  {empty_desc_count} role description(s) are blank in the export "
                    "(LinkedIn doesn't include them). Claude will generate suggestions from your resume."
                )
    else:
        print("  No LinkedIn export found. Running in resume-only mode — generating profile from scratch.")
        linkedin = None

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    if linkedin:
        prompt = f"""You are a LinkedIn profile optimisation expert. Your job is to compare a candidate's
current LinkedIn profile against their up-to-date resume and produce specific, actionable update
recommendations — not generic advice.

Writing rules:
- Write like a senior consultant. Direct and specific.
- No filler words: no "dynamic", "passionate", "results-driven", "leverage", "synergy".
- No em dashes. Use commas or full stops.
- No hedging. Say exactly what to change and why.
- Where a LinkedIn description is marked [EMPTY], write a suggested description
  based on the resume content for that role. Do not skip these — empty descriptions
  hurt recruiter discoverability.

CURRENT LINKEDIN PROFILE (from data export):
{json.dumps(linkedin)}

UP-TO-DATE RESUME (source of truth):
{json.dumps(resume)}

Analyse every section and return a JSON object with this exact structure:

{{
  "gaps_identified": [
    "Specific gap 1 — be precise, e.g. 'Apache Iceberg missing from skills' not 'skills need updating'"
  ],
  "headline": {{
    "current": "exact current headline text",
    "suggested": "exact replacement text ready to paste into LinkedIn",
    "reason": "one sentence on why this is better for recruiter search"
  }},
  "summary": {{
    "current": "first 200 chars of current summary",
    "suggested": "full replacement About section, ready to paste. 3-5 sentences. Front-load seniority and tech stack.",
    "reason": "what specifically was wrong with the current version"
  }},
  "missing_skills": [
    "Skill name exactly as it should appear in LinkedIn Skills section"
  ],
  "missing_certifications": [
    "Certification name exactly as it should appear on LinkedIn"
  ],
  "position_updates": [
    {{
      "title": "job title",
      "company": "company name",
      "current_description": "exact current description or [EMPTY]",
      "suggested_description": "full replacement description ready to paste. Lead with most impressive achievement. Use numbers where the resume has them.",
      "reason": "what is missing or wrong"
    }}
  ],
  "priority_actions": [
    "Ordered list of the 5 highest-impact changes, most important first"
  ]
}}

Return ONLY the JSON object. No other text."""
    else:
        prompt = f"""You are a LinkedIn profile optimisation expert. The candidate has no LinkedIn export available.
Your job is to generate a complete, optimised LinkedIn profile from their resume — everything ready to paste directly into LinkedIn.

Writing rules:
- Write like a senior consultant. Direct and specific.
- No filler words: no "dynamic", "passionate", "results-driven", "leverage", "synergy".
- No em dashes. Use commas or full stops.
- No hedging. Every field should be ready to paste as-is.
- Role descriptions: lead with the most impressive achievement, use numbers where the resume has them.

RESUME (source of truth):
{json.dumps(resume)}

Generate a complete LinkedIn profile and return a JSON object with this exact structure:

{{
  "gaps_identified": [
    "Any notable gaps in the resume itself that would hurt LinkedIn discoverability, e.g. missing certifications, unclear titles"
  ],
  "headline": {{
    "current": "[no export available]",
    "suggested": "exact headline text ready to paste into LinkedIn — optimised for recruiter search",
    "reason": "why this headline works for discoverability"
  }},
  "summary": {{
    "current": "[no export available]",
    "suggested": "full About section, ready to paste. 3-5 sentences. Front-load seniority and tech stack. No buzzwords.",
    "reason": "what this summary achieves"
  }},
  "missing_skills": [
    "Skills from the resume that should be added to the LinkedIn Skills section, exactly as they should appear"
  ],
  "missing_certifications": [
    "Certifications from the resume that should be added to LinkedIn, exactly as they should appear"
  ],
  "position_updates": [
    {{
      "title": "job title",
      "company": "company name",
      "current_description": "[no export available]",
      "suggested_description": "full description ready to paste. Lead with most impressive achievement. Use numbers where the resume has them.",
      "reason": "what this description achieves"
    }}
  ],
  "priority_actions": [
    "Ordered list of the 5 highest-impact things to do when setting up the LinkedIn profile, most important first"
  ]
}}

Return ONLY the JSON object. No other text."""

    print("  Comparing profile to resume...")
    last_err = None
    text = None
    for attempt in range(3):
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                text = stream.get_final_text()
            break
        except anthropic.APIConnectionError as e:
            last_err = e
            wait = 2 ** attempt
            print(f"  Connection error (attempt {attempt + 1}/3), retrying in {wait}s...")
            time.sleep(wait)
    else:
        raise last_err

    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])

    # Extract JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        text = text[start:end]

    updates = json.loads(text.strip())

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "export_age_days": age,
        "stale_warning": stale_warning,
        "status": "completed",
        "updates": updates,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return output
