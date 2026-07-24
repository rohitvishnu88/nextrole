from fastapi import APIRouter, HTTPException

from a2a import resume_history

router = APIRouter(prefix="/api/profiles", tags=["resume-versions"])


@router.get("/{slug}/resume/history")
def list_history(slug: str):
    versions = resume_history.load_history(slug)
    return [
        {"id": v["id"], "timestamp": v["timestamp"], "change_summary": v["change_summary"]}
        for v in versions
    ]


@router.get("/{slug}/resume/history/{version_id}")
def get_history_version(slug: str, version_id: str):
    version = resume_history.get_version(slug, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{slug}/resume/history/{version_id}/restore")
def restore_history_version(slug: str, version_id: str):
    restored = resume_history.restore_version(slug, version_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"restored": True, "version_id": version_id}
