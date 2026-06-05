from typing import Optional

from fastapi import APIRouter, HTTPException
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


@router.get("")
def list_applications(profile: str):
    return db.list_applications(profile)


@router.post("")
def create_application(body: ApplicationCreate):
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
    )
    apps = db.list_applications(body.profile_id)
    return next(a for a in apps if a["id"] == app_id)


@router.patch("/{app_id}")
def update_application(app_id: str, body: ApplicationPatch):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = db.update_application(app_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"updated": True}


@router.delete("/{app_id}")
def delete_application(app_id: str):
    deleted = db.delete_application(app_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"deleted": app_id}
