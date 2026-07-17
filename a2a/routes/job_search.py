import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import job_store
import job_search_agent

router = APIRouter(prefix="/api/profiles", tags=["job-search"])

_running: set = set()


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR",
                          str(Path(__file__).parent.parent.parent / "data" / "profiles"))
    return Path(base)


def _resume_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_data.json"


def _run_search(slug: str) -> None:
    try:
        resume = json.loads(_resume_file(slug).read_text(encoding="utf-8"))
        job_search_agent.run(resume, profile_slug=slug)
    finally:
        _running.discard(slug)


@router.post("/{slug}/job-search")
def start_job_search(slug: str, background_tasks: BackgroundTasks):
    if not _resume_file(slug).exists():
        raise HTTPException(status_code=404, detail="No resume data for this profile")
    if slug in _running:
        raise HTTPException(status_code=409, detail="A search is already running for this profile")
    _running.add(slug)
    background_tasks.add_task(_run_search, slug)
    return {"status": "searching"}


@router.get("/{slug}/job-search")
def get_job_search(slug: str):
    if slug in _running:
        return {"status": "searching"}
    store = job_store.load_store(slug)
    jobs = [dict(job) for job in job_store.visible_jobs(store)]
    if job_store.mark_new_as_seen(store):
        job_store.save_store(slug, store)
    return {"generated_at": store.get("generated_at", ""), "jobs": jobs}


@router.post("/{slug}/job-search/{job_id}/apply")
def apply_to_job(slug: str, job_id: str):
    store = job_store.load_store(slug)
    if not job_store.mark_status(store, job_id, "applied"):
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.save_store(slug, store)
    return {"id": job_id, "status": "applied"}


@router.post("/{slug}/job-search/{job_id}/dismiss")
def dismiss_job(slug: str, job_id: str):
    store = job_store.load_store(slug)
    if not job_store.mark_status(store, job_id, "dismissed"):
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.save_store(slug, store)
    return {"id": job_id, "status": "dismissed"}
