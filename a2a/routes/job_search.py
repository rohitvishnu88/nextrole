import json
import os
import sys
import threading
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from a2a.auth import User, current_user
from a2a.ownership import require_profile
from a2a import metering


sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import job_store
import job_search_agent

router = APIRouter(prefix="/api/profiles", tags=["job-search"])

_running: set = set()
_running_lock = threading.Lock()
_last_error: dict = {}


def _require_valid_slug(slug: str) -> None:
    try:
        job_store.validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile slug")


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR",
                          str(Path(__file__).parent.parent.parent / "data" / "profiles"))
    return Path(base)


def _resume_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_data.json"


def _search(slug: str, send_email: bool) -> None:
    resume = json.loads(_resume_file(slug).read_text(encoding="utf-8"))
    job_search_agent.run(resume, profile_slug=slug, send_email=send_email)


def _run_search(slug: str, send_email: bool = False, reservation_id: Optional[str] = None) -> None:
    _last_error.pop(slug, None)
    try:
        metering.run(reservation_id, _search, slug, send_email)
    except Exception as e:
        _last_error[slug] = str(e)
    finally:
        _running.discard(slug)


@router.post("/{slug}/job-search")
def start_job_search(slug: str, background_tasks: BackgroundTasks, user: User = Depends(current_user)):
    require_profile(slug, user)
    _require_valid_slug(slug)
    if not _resume_file(slug).exists():
        raise HTTPException(status_code=404, detail="No resume data for this profile")
    with _running_lock:
        if slug in _running:
            raise HTTPException(status_code=409, detail="A search is already running for this profile")
        _running.add(slug)
    try:
        reservation_id = metering.start(user, "job_search")
    except HTTPException:
        _running.discard(slug)
        raise
    # The results email goes to the owner's inbox, so only the owner's own searches send it.
    background_tasks.add_task(_run_search, slug, user.is_owner, reservation_id)
    return {"status": "searching"}


@router.get("/{slug}/job-search")
def get_job_search(slug: str, user: User = Depends(current_user)):
    require_profile(slug, user)
    _require_valid_slug(slug)
    if slug in _running:
        return {"status": "searching"}
    store = job_store.load_store(slug)
    jobs = [dict(job) for job in job_store.visible_jobs(store)]
    if job_store.mark_new_as_seen(store):
        job_store.save_store(slug, store)
    return {
        "generated_at": store.get("generated_at", ""),
        "jobs": jobs,
        "error": _last_error.get(slug),
    }


@router.post("/{slug}/job-search/{job_id}/apply")
def apply_to_job(slug: str, job_id: str, user: User = Depends(current_user)):
    require_profile(slug, user)
    _require_valid_slug(slug)
    store = job_store.load_store(slug)
    if not job_store.mark_status(store, job_id, "applied"):
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.save_store(slug, store)
    return {"id": job_id, "status": "applied"}


@router.post("/{slug}/job-search/{job_id}/dismiss")
def dismiss_job(slug: str, job_id: str, user: User = Depends(current_user)):
    require_profile(slug, user)
    _require_valid_slug(slug)
    store = job_store.load_store(slug)
    if not job_store.mark_status(store, job_id, "dismissed"):
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.save_store(slug, store)
    return {"id": job_id, "status": "dismissed"}
