import json as _json
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from a2a import resume_history

router = APIRouter(prefix="/api/profiles", tags=["resume-versions"])

LIST_OBJECT_SECTIONS = ("experience", "education", "certifications")
FLAT_LIST_SECTIONS = ("languages",)
GROUPED_LIST_SECTIONS = ("skills",)
SCALAR_SECTIONS = ("name", "designation", "work_right", "email", "phone", "website", "summary")


def _require_valid_slug(slug: str) -> None:
    try:
        resume_history.validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile slug")

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


class SectionDraft(BaseModel):
    action: str
    item_index: Optional[int] = None
    group: Optional[str] = None
    skill: Optional[str] = None
    instruction: str


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


def _draft_prompt_list_object(resume: dict, section: str, body: SectionDraft) -> str:
    items = resume.get(section, [])
    if body.action == "edit":
        if body.item_index is None or not (0 <= body.item_index < len(items)):
            raise HTTPException(status_code=400, detail="item_index out of range")
        current = items[body.item_index]
        return f"""You are editing one entry in the "{section}" section of a resume.

Current entry:
{_json.dumps(current, indent=2)}

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": <the revised entry, same fields as the current entry>}}. Keep every field the current entry has; change only what the request asks for. Do not invent information not present in the current entry or the request."""

    if body.action == "add":
        example = items[0] if items else FALLBACK_SCHEMA[section]
        return f"""You are adding one or more new entries to the "{section}" section of a resume.

Existing entries follow this shape (example):
{_json.dumps(example, indent=2)}

Requested addition: {body.instruction}

Return ONLY a JSON object of the form {{"items": [<new entry>, ...]}} - one object per new entry described in the request, each matching the example's fields exactly. Use only information present in the request. Do not invent details."""

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _draft_prompt_flat_list(resume: dict, section: str, body: SectionDraft) -> str:
    items = resume.get(section, [])
    if body.action == "edit":
        if body.item_index is None or not (0 <= body.item_index < len(items)):
            raise HTTPException(status_code=400, detail="item_index out of range")
        current = items[body.item_index]
        return f"""You are editing one entry in the "{section}" section of a resume (a plain list of short text values).

Current value: "{current}"

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": "<revised value>"}}."""

    if body.action == "add":
        return f"""You are adding one or more new entries to the "{section}" section of a resume (a plain list of short text values).

Requested addition: {body.instruction}

Return ONLY a JSON object of the form {{"items": ["<value>", ...]}} - one string per new entry described in the request."""

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _draft_prompt_grouped_list(resume: dict, section: str, body: SectionDraft) -> str:
    skills = resume.get("skills", {})
    existing_groups = list(skills.keys())

    if body.action == "edit":
        if body.group is None or body.skill is None:
            raise HTTPException(status_code=400, detail="group and skill are required")
        if body.group not in skills or body.skill not in skills[body.group]:
            raise HTTPException(status_code=400, detail="skill not found in group")
        return f"""You are editing one skill in a resume's Skills section.

Current skill: "{body.skill}" in group "{body.group}"

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": {{"group": "<group name>", "skill": "<skill name>"}}}}."""

    if body.action == "add":
        return f"""You are adding one or more new skills to a resume's Skills section.

Existing groups: {_json.dumps(existing_groups)}

Requested addition: {body.instruction}

Return ONLY a JSON object of the form {{"items": [{{"group": "<group name>", "skill": "<skill name>"}}, ...]}} - one entry per new skill described in the request. Reuse an existing group name where it fits; otherwise use a new, concise group name."""

    raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")


def _draft_prompt_scalar(resume: dict, section: str, body: SectionDraft) -> str:
    if body.action != "edit":
        raise HTTPException(status_code=400, detail=f"{section} only supports the edit action")
    current = resume.get(section, "")
    return f"""You are editing the "{section}" field of a resume.

Current value: "{current}"

Requested change: {body.instruction}

Return ONLY a JSON object of the form {{"item": "<revised value>"}}."""


DRAFT_PROMPT_BUILDERS = {
    "list_object": _draft_prompt_list_object,
    "flat_list": _draft_prompt_flat_list,
    "grouped_list": _draft_prompt_grouped_list,
    "scalar": _draft_prompt_scalar,
}


@router.get("/{slug}/resume/history")
def list_history(slug: str):
    _require_valid_slug(slug)
    versions = resume_history.load_history(slug)
    return [
        {"id": v["id"], "timestamp": v["timestamp"], "change_summary": v["change_summary"]}
        for v in versions
    ]


@router.get("/{slug}/resume/history/{version_id}")
def get_history_version(slug: str, version_id: str):
    _require_valid_slug(slug)
    version = resume_history.get_version(slug, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{slug}/resume/history/{version_id}/restore")
def restore_history_version(slug: str, version_id: str):
    _require_valid_slug(slug)
    restored = resume_history.restore_version(slug, version_id)
    if restored is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"restored": True, "version_id": version_id}


@router.post("/{slug}/resume/sections/{section}/apply")
def apply_section(slug: str, section: str, body: SectionApply):
    _require_valid_slug(slug)
    kind = _section_kind(section)
    resume = resume_history.load_current(slug)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    change_summary = APPLY_HANDLERS[kind](resume, section, body)

    resume_history.push_version(slug, change_summary)
    resume_history.save_current(slug, resume)
    return {"saved": True, "change_summary": change_summary}


@router.post("/{slug}/resume/sections/{section}/draft")
def draft_section(slug: str, section: str, body: SectionDraft):
    _require_valid_slug(slug)
    import anthropic
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
    from config import MODEL, extract_json_object

    kind = _section_kind(section)
    resume = resume_history.load_current(slug)
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume data for this profile")

    prompt = DRAFT_PROMPT_BUILDERS[kind](resume, section, body)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        parsed = _json.loads(extract_json_object(response.content[0].text))
    except _json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Could not parse the AI's draft. Try rephrasing the instruction.")

    # Validate shape matches the action
    if body.action == "add":
        if "items" not in parsed or not isinstance(parsed["items"], list):
            raise HTTPException(status_code=500, detail="AI response did not match the expected shape (expected 'items' list). Try rephrasing the instruction.")
    elif body.action == "edit":
        if "item" not in parsed:
            raise HTTPException(status_code=500, detail="AI response did not match the expected shape (expected 'item'). Try rephrasing the instruction.")

    return parsed
