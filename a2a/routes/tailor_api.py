import asyncio
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from a2a.auth import User, current_user
from a2a.ownership import require_profile
from a2a import metering

from fastapi.responses import FileResponse
from pydantic import BaseModel

from a2a import resume_history

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
from resume_builder import render_resume

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import job_analysis

ROOT = Path(__file__).parent.parent.parent

router = APIRouter(prefix="/api/tailor", tags=["tailor"])

_jobs = {}

# Tailor output filenames are built from agents/tailor_agent.py::slugify(),
# which only ever produces lowercase letters, digits, and underscores.
_ENTRY_ID_RE = re.compile(r"^[a-z0-9_]+$")


def _require_valid_profile_slug(slug: str) -> None:
    try:
        resume_history.validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile slug")


def _require_valid_entry_id(entry_id: str) -> None:
    if not _ENTRY_ID_RE.match(entry_id):
        raise HTTPException(status_code=400, detail="Invalid history entry id")


class TailorRequest(BaseModel):
    profile_slug: str
    url: Optional[str] = None
    jd_text: Optional[str] = None


class UpdateRequest(BaseModel):
    resume: dict
    cover_letter: Optional[str] = None


@router.post("")
async def start_tailor(body: TailorRequest, user: User = Depends(current_user)):
    require_profile(body.profile_slug, user)
    if not body.url and not body.jd_text:
        raise HTTPException(status_code=400, detail="Provide either 'url' or 'jd_text'")

    reservation_id = metering.start(user, "tailor")
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "message": "Starting...", "profile_slug": body.profile_slug, "user_id": user.id}

    def _tailor() -> dict:
        import tailor_agent
        result = tailor_agent.run(job_url=body.url or "", jd_text=body.jd_text or "", profile_slug=body.profile_slug)
        if result["status"] != "completed":
            # A run that couldn't finish shouldn't use up the allowance.
            raise RuntimeError(result.get("reason", "Unknown error"))
        return result

    async def _run():
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
        import tailor_agent
        loop = asyncio.get_event_loop()
        _jobs[job_id]["message"] = "Fetching job description..."
        try:
            result = await loop.run_in_executor(None, lambda: metering.run(reservation_id, _tailor))
            if result["status"] == "completed":
                _jobs[job_id].update({
                    "status": "completed",
                    "message": "Done",
                    "pdf_file": result["pdf_file"],
                    "cover_letter_file": result["cover_letter_file"],
                    "json_file": result["json_file"],
                    "fit_file": result.get("fit_file"),
                    "base_file": result.get("base_file"),
                    "analysis_id": result.get("analysis_id"),
                    "url": body.url or "",
                })
            else:
                _jobs[job_id].update({"status": "failed", "message": result.get("reason", "Unknown error")})
        except Exception as e:
            _jobs[job_id].update({"status": "failed", "message": str(e)})

    asyncio.create_task(_run())
    return {"job_id": job_id}


def _load_analysis_or_none(profile_slug: str, analysis_id: Optional[str]) -> Optional[dict]:
    if not analysis_id or not job_analysis.ANALYSIS_ID_RE.match(analysis_id):
        return None
    return job_analysis.load_analysis(profile_slug, analysis_id)


def _recheck_fit(job: dict) -> Optional[dict]:
    fit_file, base_file = job.get("fit_file"), job.get("base_file")
    if not fit_file or not base_file or not Path(fit_file).exists() or not Path(base_file).exists():
        return None
    import tailor_agent
    return tailor_agent.recheck_fit(job["json_file"], job["pdf_file"], base_file, fit_file)


@router.get("/history/{profile_slug}")
def list_tailor_history(profile_slug: str, user: User = Depends(current_user)):
    require_profile(profile_slug, user)
    """List every past tailoring run for a profile by scanning the output
    directory directly - the in-memory `_jobs` dict above only holds jobs
    from the current server process and is lost on restart, but the actual
    PDF/JSON/cover-letter files persist on disk indefinitely."""
    _require_valid_profile_slug(profile_slug)

    resumes_dir = ROOT / "output" / "profiles" / profile_slug / "resumes"
    cover_letters_dir = ROOT / "output" / "profiles" / profile_slug / "cover_letters"
    if not resumes_dir.exists():
        return []

    entries = []
    for json_path in resumes_dir.glob("resume_data_*.json"):
        entry_id = json_path.stem[len("resume_data_"):]
        pdf_path = resumes_dir / f"resume_{entry_id}.pdf"
        meta_path = resumes_dir / f"meta_{entry_id}.json"
        cover_letter_path = cover_letters_dir / f"cover_letter_{entry_id}.txt"

        job_url = ""
        created_at = datetime.fromtimestamp(json_path.stat().st_mtime, tz=timezone.utc).isoformat()
        analysis = None
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            job_url = meta.get("job_url") or ""
            created_at = meta.get("created_at") or created_at
            analysis = _load_analysis_or_none(profile_slug, meta.get("analysis_id"))

        entries.append({
            "id": entry_id,
            "created_at": created_at,
            "job_url": job_url,
            "pdf_available": pdf_path.exists(),
            "cover_letter_available": cover_letter_path.exists(),
            "match_score": analysis.get("match_score") if analysis else None,
            "verdict": analysis.get("verdict") if analysis else None,
        })

    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries


@router.get("/history/{profile_slug}/{entry_id}/pdf")
def download_history_pdf(profile_slug: str, entry_id: str, user: User = Depends(current_user)):
    require_profile(profile_slug, user)
    _require_valid_profile_slug(profile_slug)
    _require_valid_entry_id(entry_id)
    path = ROOT / "output" / "profiles" / profile_slug / "resumes" / f"resume_{entry_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/history/{profile_slug}/{entry_id}/cover-letter")
def download_history_cover_letter(profile_slug: str, entry_id: str, user: User = Depends(current_user)):
    require_profile(profile_slug, user)
    _require_valid_profile_slug(profile_slug)
    _require_valid_entry_id(entry_id)
    path = ROOT / "output" / "profiles" / profile_slug / "cover_letters" / f"cover_letter_{entry_id}.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter file not found on disk")
    return FileResponse(path, media_type="text/plain", filename=path.name)


def _owned_job(job_id: str, user: User) -> Optional[dict]:
    """The job if this user started it, else None (so callers answer 404)."""
    job = _jobs.get(job_id)
    if not job:
        return None
    owner = job.get("user_id")
    return job if (owner == user.id if owner else user.is_owner) else None


@router.get("/{job_id}")
def get_tailor_status(job_id: str, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
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
def get_tailor_data(job_id: str, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    json_path = Path(job["json_file"])
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Resume JSON not found on disk")
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/{job_id}/cover-letter-text")
def get_cover_letter_text(job_id: str, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    path = Path(job["cover_letter_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter not found on disk")
    return {"text": path.read_text(encoding="utf-8")}


@router.patch("/{job_id}/data")
def update_tailor_data(job_id: str, body: UpdateRequest, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")

    json_path = Path(job["json_file"])
    pdf_path = Path(job["pdf_file"])
    html_path = pdf_path.with_suffix(".html")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(body.resume, f, indent=2)

    render_resume(body.resume, str(html_path), str(pdf_path))

    if body.cover_letter is not None:
        Path(job["cover_letter_file"]).write_text(body.cover_letter, encoding="utf-8")

    return {"ok": True, "fit": _recheck_fit(job)}


@router.get("/{job_id}/fit")
def get_tailor_fit(job_id: str, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    fit_file = job.get("fit_file")
    if not fit_file or not Path(fit_file).exists():
        raise HTTPException(status_code=404, detail="No fit results for this run")
    fit = json.loads(Path(fit_file).read_text(encoding="utf-8"))
    return {
        "analysis": _load_analysis_or_none(job.get("profile_slug", ""), fit.get("analysis_id")),
        "changes": fit.get("changes", []),
        "fabrication_flags": fit.get("fabrication_flags", []),
        "ats": fit.get("ats", {}),
    }


@router.get("/{job_id}/pdf")
def download_pdf(job_id: str, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="PDF not ready")
    path = Path(job["pdf_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/{job_id}/cover-letter")
def download_cover_letter(job_id: str, user: User = Depends(current_user)):
    job = _owned_job(job_id, user)
    if not job or job["status"] != "completed":
        raise HTTPException(status_code=404, detail="Cover letter not ready")
    path = Path(job["cover_letter_file"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover letter file not found on disk")
    return FileResponse(path, media_type="text/plain", filename=path.name)
