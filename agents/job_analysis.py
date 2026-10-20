"""Decode a job ad and score the candidate against it, using Rohit's own prompts.

Results are cached per (job text, base resume) so the same ad is never analysed twice.
"""
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(Path(__file__).parent))
from config import MODEL, extract_json_object
from job_score import compute_match_score
from job_store import validate_slug

MIN_JD_CHARS = 400
ANALYSIS_ID_RE = re.compile(r"^[a-f0-9]{16}$")

LIKELIHOODS = ("high", "medium", "low", "filler")
MEETS = ("yes", "partly", "no")
VERDICTS = ("strong fit", "genuine stretch", "waste of time")

DECODE_PROMPT = """Tell me:
- what this job actually is, underneath the language
- which requirements are real and which are filler pasted from an old ad
- what problem they are hiring to solve, and what that suggests went wrong before
- the exact words someone would search for, taken from this ad
- anything suspicious: contradictions, an impossible mix of skills, signs the role was written around someone they already have

Rank the requirements by how likely each is to be a real filter."""

SCORE_PROMPT = """Score me honestly. For each real requirement, tell me:
- do I meet it, partly meet it, or not at all
- what in my resume backs that up
- what I would say in an interview about the gap

Then tell me:
- the three gaps that matter, and which ones do not
- whether this is a genuine stretch or a waste of my time
- what I could truthfully add that I have simply left off

Be blunt."""

SCHEMA = """Return ONLY a JSON object with exactly these fields:
{
  "what_it_really_is": "short paragraph",
  "problem_being_solved": "paragraph, including what that suggests went wrong before",
  "search_terms": ["exact phrases taken from the ad"],
  "suspicious": ["contradictions, impossible skill mixes, signs it was written around an existing person"],
  "requirements": [
    {
      "text": "the requirement",
      "filter_likelihood": "high | medium | low | filler",
      "why": "why you ranked it that way",
      "key_terms": ["short exact phrases from the ad for this requirement"],
      "meets": "yes | partly | no",
      "evidence": "quote from my resume that backs it up, or empty",
      "interview_answer": "what I would say in an interview about the gap"
    }
  ],
  "gaps_that_matter": ["at most three"],
  "gaps_that_dont": ["..."],
  "verdict": "strong fit | genuine stretch | waste of time",
  "verdict_reason": "one or two sentences",
  "left_off": ["things I may have done but left off, phrased as questions for me to confirm, never as facts"]
}
Order requirements from most to least likely to be a real filter."""


class JobTextTooShort(Exception):
    pass


def _normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def make_analysis_id(jd_text: str, resume: dict) -> str:
    resume_hash = hashlib.sha256(json.dumps(resume, sort_keys=True).encode()).hexdigest()
    return hashlib.sha256((_normalise_text(jd_text) + "\n" + resume_hash).encode()).hexdigest()[:16]


def _str(value) -> str:
    return value if isinstance(value, str) else ""


def _str_list(value) -> List[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def normalise_analysis(raw: dict) -> dict:
    requirements = []
    for req in raw.get("requirements") if isinstance(raw.get("requirements"), list) else []:
        if not isinstance(req, dict):
            continue
        likelihood = req.get("filter_likelihood")
        meets = req.get("meets")
        requirements.append({
            "text": _str(req.get("text")),
            "filter_likelihood": likelihood if likelihood in LIKELIHOODS else "low",
            "why": _str(req.get("why")),
            "key_terms": _str_list(req.get("key_terms")),
            "meets": meets if meets in MEETS else "no",
            "evidence": _str(req.get("evidence")),
            "interview_answer": _str(req.get("interview_answer")),
        })
    verdict = raw.get("verdict")
    return {
        "what_it_really_is": _str(raw.get("what_it_really_is")),
        "problem_being_solved": _str(raw.get("problem_being_solved")),
        "search_terms": _str_list(raw.get("search_terms")),
        "suspicious": _str_list(raw.get("suspicious")),
        "requirements": requirements,
        "gaps_that_matter": _str_list(raw.get("gaps_that_matter"))[:3],
        "gaps_that_dont": _str_list(raw.get("gaps_that_dont")),
        "verdict": verdict if verdict in VERDICTS else "genuine stretch",
        "verdict_reason": _str(raw.get("verdict_reason")),
        "left_off": _str_list(raw.get("left_off")),
    }


def analyse_job(client, resume: dict, jd_text: str) -> dict:
    if len(_normalise_text(jd_text)) < MIN_JD_CHARS:
        raise JobTextTooShort("Couldn't read the full job ad. Paste the job description text instead.")

    prompt = f"""You are helping a candidate decide how well they fit a job and what to do about the gaps.

Here is a job ad:

{jd_text}

{DECODE_PROMPT}

Here is my resume:

{json.dumps(resume, indent=2)}

{SCORE_PROMPT}

{SCHEMA}"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = json.loads(extract_json_object(response.content[0].text))
    analysis = normalise_analysis(raw if isinstance(raw, dict) else {})
    analysis["match_score"] = compute_match_score(analysis["requirements"])
    analysis["analysis_id"] = make_analysis_id(jd_text, resume)
    analysis["created_at"] = datetime.now().astimezone().isoformat()
    return analysis


def analysis_path(profile_slug: str, analysis_id: str) -> Path:
    if not profile_slug:
        raise ValueError("profile_slug is required")
    validate_slug(profile_slug)
    if not ANALYSIS_ID_RE.match(analysis_id or ""):
        raise ValueError(f"invalid analysis_id: {analysis_id!r}")
    return ROOT / "output" / "profiles" / profile_slug / "analyses" / f"{analysis_id}.json"


def load_analysis(profile_slug: str, analysis_id: str) -> Optional[dict]:
    path = analysis_path(profile_slug, analysis_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_analysis(profile_slug: str, analysis: dict) -> None:
    path = analysis_path(profile_slug, analysis["analysis_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")


def get_or_create_analysis(client, profile_slug: str, resume: dict, jd_text: str) -> dict:
    cached = load_analysis(profile_slug, make_analysis_id(jd_text, resume))
    if cached is not None:
        return cached
    analysis = analyse_job(client, resume, jd_text)
    save_analysis(profile_slug, analysis)
    return analysis
