from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from a2a import resume_history

router = APIRouter(prefix="/api/profiles", tags=["resume-versions"])

LIST_OBJECT_SECTIONS = ("experience", "education", "certifications")
FLAT_LIST_SECTIONS = ("languages",)
GROUPED_LIST_SECTIONS = ("skills",)
SCALAR_SECTIONS = ("name", "designation", "work_right", "email", "phone", "website", "summary")

TITLE_FIELD = {"experience": "title", "education": "degree", "certifications": "name"}

SECTION_LABELS = {
    "experience": "Experience", "education": "Education", "certifications": "Certifications",
    "languages": "Languages", "skills": "Skills",
    "name": "Name", "designation": "Designation", "work_right": "Work Right", "email": "Email",
    "phone": "Phone", "website": "Website", "summary": "Summary",
}

FALLBACK_SCHEMA = {
    "experience": {"title": "", "highlight": "", "company": "", "location": "", "start_date": "", "end_date": "", "description": []},
    "education": {"degree": "", "school": "", "location": "", "start_date": "", "end_date": "", "gpa": ""},
    "certifications": {"name": "", "issuer": ""},
}


def _section_kind(section: str) -> str:
    if section in LIST_OBJECT_SECTIONS:
        return "list_object"
    if section in FLAT_LIST_SECTIONS:
        return "flat_list"
    if section in GROUPED_LIST_SECTIONS:
        return "grouped_list"
    if section in SCALAR_SECTIONS:
        return "scalar"
    raise HTTPException(status_code=400, detail=f"Unknown section: {section}")


class SectionApply(BaseModel):
    action: str
    item_index: Optional[int] = None
    group: Optional[str] = None
    skill: Optional[str] = None
    item: Optional[Any] = None


def _apply_list_object(resume: dict, section: str, body: SectionApply) -> str:
    items = resume.setdefault(section, [])
    title_field = TITLE_FIELD[section]
    label = SECTION_LABELS[section]

    if body.action == "add":
        new_items = body.item if isinstance(body.item, list) else [body.item]
        if not new_items:
            raise HTTPException(status_code=400, detail="No items to add")
        items.extend(new_items)
        names = ", ".join(str(i.get(title_field, "")) for i in new_items)
        return f"Added {label}: {names}"

    if body.item_index is None or not (0 <= body.item_index < len(items)):
        raise HTTPException(status_code=400, detail="item_index out of range")

    if body.action == "edit":
        if not isinstance(body.item, dict):
            raise HTTPException(status_code=400, detail="item must be an object")
        items[body.item_index] = body.item
        return f"Edited {label}: {body.item.get(title_field, '')}"

    if body.action == "delete":
        removed = items.pop(body.item_index)
        return f"Deleted {label}: {removed.get(title_field, '')}"

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _apply_flat_list(resume: dict, section: str, body: SectionApply) -> str:
    items = resume.setdefault(section, [])
    label = SECTION_LABELS[section]

    if body.action == "add":
        new_items = body.item if isinstance(body.item, list) else [body.item]
        if not new_items:
            raise HTTPException(status_code=400, detail="No items to add")
        items.extend(str(i) for i in new_items)
        return f"Added {label}: {', '.join(str(i) for i in new_items)}"

    if body.item_index is None or not (0 <= body.item_index < len(items)):
        raise HTTPException(status_code=400, detail="item_index out of range")

    if body.action == "edit":
        items[body.item_index] = str(body.item)
        return f"Edited {label}: {body.item}"

    if body.action == "delete":
        removed = items.pop(body.item_index)
        return f"Deleted {label}: {removed}"

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _apply_grouped_list(resume: dict, section: str, body: SectionApply) -> str:
    skills = resume.setdefault("skills", {})

    if body.action == "add":
        new_items = body.item if isinstance(body.item, list) else [body.item]
        if not new_items:
            raise HTTPException(status_code=400, detail="No items to add")
        groups_touched = []
        for entry in new_items:
            if not isinstance(entry, dict) or "group" not in entry or "skill" not in entry:
                raise HTTPException(status_code=400, detail="Each item must be an object with group and skill keys")
            group, skill = entry["group"], entry["skill"]
            skills.setdefault(group, []).append(skill)
            if group not in groups_touched:
                groups_touched.append(group)
        return f"Added Skills: {', '.join(groups_touched)}"

    if body.group is None or body.skill is None:
        raise HTTPException(status_code=400, detail="group and skill are required")
    if body.group not in skills or body.skill not in skills[body.group]:
        raise HTTPException(status_code=400, detail="skill not found in group")

    if body.action == "edit":
        if not isinstance(body.item, dict):
            raise HTTPException(status_code=400, detail="item must be an object")
        if "group" not in body.item or "skill" not in body.item:
            raise HTTPException(status_code=400, detail="item must have group and skill keys")
        new_group, new_skill = body.item["group"], body.item["skill"]
        skills[body.group].remove(body.skill)
        if not skills[body.group]:
            del skills[body.group]
        skills.setdefault(new_group, []).append(new_skill)
        return f"Edited Skills: {body.group}"

    if body.action == "delete":
        skills[body.group].remove(body.skill)
        if not skills[body.group]:
            del skills[body.group]
        return f"Deleted Skills: {body.group}"

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _apply_scalar(resume: dict, section: str, body: SectionApply) -> str:
    if body.action != "edit":
        raise HTTPException(status_code=400, detail=f"{section} only supports the edit action")
    resume[section] = body.item
    return f"Edited {SECTION_LABELS[section]}"


APPLY_HANDLERS = {
    "list_object": _apply_list_object,
    "flat_list": _apply_flat_list,
    "grouped_list": _apply_grouped_list,
    "scalar": _apply_scalar,
}


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


@router.post("/{slug}/resume/sections/{section}/apply")
def apply_section(slug: str, section: str, body: SectionApply):
    kind = _section_kind(section)
    resume = resume_history.load_current(slug)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    change_summary = APPLY_HANDLERS[kind](resume, section, body)

    resume_history.push_version(slug, change_summary)
    resume_history.save_current(slug, resume)
    return {"saved": True, "change_summary": change_summary}
