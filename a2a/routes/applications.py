from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from a2a.auth import User, current_user
from a2a.ownership import require_profile

from pydantic import BaseModel

from a2a import db

router = APIRouter(prefix="/api/applications", tags=["applications"])


class ApplicationCreate(BaseModel):
    profile_id: str
    job_title: str
    company: str
    location: Optional[str] = None
    url: Optional[str] = None
    status: str = "saved"
    applied_date: Optional[str] = None
    notes: Optional[str] = None
    resume_file: Optional[str] = None
    cover_letter_file: Optional[str] = None
    follow_up_date: Optional[str] = None
    match_score: Optional[int] = None
    analysis_id: Optional[str] = None


class ApplicationPatch(BaseModel):
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None
    applied_date: Optional[str] = None
    notes: Optional[str] = None
    resume_file: Optional[str] = None
    cover_letter_file: Optional[str] = None
    follow_up_date: Optional[str] = None


def _owned_application(app_id: str, user: User) -> dict:
    row = db.get_application(app_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found")
    try:
        require_profile(row["profile_id"], user)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Application not found")
    return row


@router.get("")
def list_applications(profile: str, user: User = Depends(current_user)):
    require_profile(profile, user)
    return db.list_applications(profile)


@router.post("")
def create_application(body: ApplicationCreate, user: User = Depends(current_user)):
    require_profile(body.profile_id, user)
    app_id = db.create_application(
        profile_id=body.profile_id,
        job_title=body.job_title,
        company=body.company,
        location=body.location,
        url=body.url,
        status=body.status,
        applied_date=body.applied_date,
        notes=body.notes,
        resume_file=body.resume_file,
        cover_letter_file=body.cover_letter_file,
        follow_up_date=body.follow_up_date,
        match_score=body.match_score,
        analysis_id=body.analysis_id,
    )
    apps = db.list_applications(body.profile_id)
    return next(a for a in apps if a["id"] == app_id)


@router.patch("/{app_id}")
def update_application(app_id: str, body: ApplicationPatch, user: User = Depends(current_user)):
    _owned_application(app_id, user)
    # Only fields the client actually sent, so an explicit null clears a value.
    fields = {k: getattr(body, k) for k in body.model_fields_set}
    if any(fields.get(k, "") is None for k in ("job_title", "company", "status")):
        raise HTTPException(status_code=400, detail="job_title, company and status cannot be cleared")
    updated = db.update_application(app_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"updated": True}


@router.post("/{app_id}/followed-up")
def mark_followed_up(app_id: str, user: User = Depends(current_user)):
    _owned_application(app_id, user)
    next_date = (date.today() + timedelta(days=db.FOLLOW_UP_DAYS)).isoformat()
    if not db.update_application(app_id, {"follow_up_date": next_date}):
        raise HTTPException(status_code=404, detail="Application not found")
    return {"follow_up_date": next_date}


@router.delete("/{app_id}")
def delete_application(app_id: str, user: User = Depends(current_user)):
    _owned_application(app_id, user)
    deleted = db.delete_application(app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": app_id}
