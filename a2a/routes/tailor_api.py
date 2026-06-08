import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
from resume_builder import render_resume

router = APIRouter(prefix="/api/tailor", tags=["tailor"])

_jobs = {}


class TailorRequest(BaseModel):
    profile_slug: str
    url: Optional[str] = None
    jd_text: Optional[str] = None


@router.post("")
async def start_tailor(body: TailorRequest):
    if not body.url and not body.jd_text:
        raise HTTPException(status_code=400, detail="Provide either 'url' or 'jd_text'")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "message": "Starting...", "profile_slug": body.profile_slug}

    async def _run():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
        import tailor_agent
        loop = asyncio.get_event_loop()
        _jobs[job_id]["message"] = "Fetching job description..."
        try:
            result = await loop.run_in_executor(
                None,
                lambda: tailor_agent.run(
                    job_url=body.url or "",
                    jd_text=body.jd_text or "",
                    profile_slug=body.profile_slug,
                ),
            )
            if result["status"] == "completed":
                _jobs[job_id].update({
                    "status": "completed",
                    "message": "Done",
                    "pdf_file": result["pdf_file"],
                    "cover_letter_file": result["cover_letter_file"],
                    "json_file": result["json_file"],
                    "url": body.url or "",
                })
            else:
                _jobs[job_id].update({"status": "failed", "message": result.get("reason", "Unknown error")})
        except Exception as e:
            _jobs[job_id].update({"status": "failed", "message": str(e)})

    asyncio.create_task(_run())
    return {"job_id": job_id}


@router.get("/{job_id}")
def get_tailor_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "message": job.get("message", ""),
        "pdf_file": job.get("pdf_file"),
        "cover_letter_file": job.get("cover_letter_file"),
        "json_file": job.get("json_file"),
        "url": job.get("url", ""),
    }


@router.get("/{job_id}/data")
def get_tailor_data(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    json_path = Path(job["json_file"])
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Resume JSON not found on disk")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/{job_id}/pdf")
def download_pdf(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="PDF not ready")
    path = Path(job["pdf_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/{job_id}/cover-letter")
def download_cover_letter(job_id: str):
    job = _jobs.get(job_id)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Cover letter not ready")
    path = Path(job["cover_letter_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter file not found on disk")
    return FileResponse(path, media_type="text/plain", filename=path.name)
