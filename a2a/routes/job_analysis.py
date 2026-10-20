import json
import os
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from a2a.auth import User, current_user
from a2a.ownership import require_profile


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import job_analysis
import job_store

router = APIRouter(prefix="/api/profiles", tags=["job-analysis"])

_running: set = set()
_running_lock = threading.Lock()
_last_error: dict = {}


def _require_valid_slug(slug: str) -> None:
    try:
        job_store.validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile slug")


def _resume_file(slug: str) -> Path:
    base = os.environ.get("PROFILES_DIR", str(Path(__file__).parent.parent.parent / "data" / "profiles"))
    return Path(base) / slug / "resume_data.json"


def _fetch_job_text_with_source(url: str):
    import tailor_agent
    return tailor_agent.fetch_job_description_with_source(url)


def _make_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _find_job(slug: str, job_id: str) -> dict:
    job = job_store.load_store(slug).get("jobs", {}).get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _run_analysis(slug: str, job_id: str, url: str) -> None:
    key = (slug, job_id)
    _last_error.pop(key, None)
    try:
        resume = json.loads(_resume_file(slug).read_text(encoding="utf-8"))
        jd_text, source = _fetch_job_text_with_source(url)
        if source == "search":
            raise job_analysis.JobTextTooShort(
                "Only a search snippet was found for this job, not the full ad. Tailor it with the ad text pasted instead.")
        analysis = job_analysis.get_or_create_analysis(_make_client(), slug, resume, jd_text, source_url=url)
        store = job_store.load_store(slug)
        job_store.set_analysis(store, job_id, analysis["analysis_id"])
        job_store.save_store(slug, store)
    except Exception as e:
        _last_error[key] = str(e)
    finally:
        _running.discard(key)


@router.post("/{slug}/job-search/{job_id}/analyse")
def start_job_analysis(slug: str, job_id: str, background_tasks: BackgroundTasks, user: User = Depends(current_user)):
    require_profile(slug, user)
    _require_valid_slug(slug)
    job = _find_job(slug, job_id)
    with _running_lock:
        if (slug, job_id) in _running:
            return {"status": "analysing"}
        _running.add((slug, job_id))
    background_tasks.add_task(_run_analysis, slug, job_id, job["url"])
    return {"status": "analysing"}


@router.get("/{slug}/job-search/{job_id}/analysis")
def get_job_analysis(slug: str, job_id: str, user: User = Depends(current_user)):
    require_profile(slug, user)
    _require_valid_slug(slug)
    if (slug, job_id) in _running:
        return {"status": "analysing"}
    if (slug, job_id) in _last_error:
        return {"status": "failed", "error": _last_error[(slug, job_id)]}
    analysis_id = _find_job(slug, job_id).get("analysis_id")
    analysis = job_analysis.load_analysis(slug, analysis_id) if analysis_id else None
    if analysis is None:
        return {"status": "none"}
    return {"status": "ready", "analysis": analysis}
