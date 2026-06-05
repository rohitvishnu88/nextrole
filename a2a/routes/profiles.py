import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

_PARSE_CACHE: Dict[str, dict] = {}


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR", str(Path(__file__).parent.parent.parent / "data" / "profiles"))
    return Path(base)


def _meta_file() -> Path:
    return _profiles_dir() / "profiles.json"


def _load_meta() -> List[dict]:
    f = _meta_file()
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))


def _save_meta(profiles: List[dict]) -> None:
    _profiles_dir().mkdir(parents=True, exist_ok=True)
    _meta_file().write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


class ProfileCreate(BaseModel):
    name: str
    slug: str = ""


class ProfilePatch(BaseModel):
    name: str


@router.get("")
def list_profiles():
    return _load_meta()


@router.post("")
def create_profile(body: ProfileCreate):
    profiles = _load_meta()
    slug = body.slug or _slugify(body.name)
    if any(p["slug"] == slug for p in profiles):
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' already exists")
    profile = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "slug": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    profiles.append(profile)
    _save_meta(profiles)
    profile_dir = _profiles_dir() / slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile


@router.patch("/{slug}")
def update_profile(slug: str, body: ProfilePatch):
    profiles = _load_meta()
    for p in profiles:
        if p["slug"] == slug:
            p["name"] = body.name
            _save_meta(profiles)
            return p
    raise HTTPException(status_code=404, detail="Profile not found")


@router.delete("/{slug}")
def delete_profile(slug: str):
    import shutil
    profiles = _load_meta()
    updated = [p for p in profiles if p["slug"] != slug]
    if len(updated) == len(profiles):
        raise HTTPException(status_code=404, detail="Profile not found")
    _save_meta(updated)
    profile_dir = _profiles_dir() / slug
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    return {"deleted": slug}


@router.get("/{slug}/resume")
def get_resume(slug: str):
    resume_file = _profiles_dir() / slug / "resume_data.json"
    if not resume_file.exists():
        raise HTTPException(status_code=404, detail="No resume data for this profile")
    return json.loads(resume_file.read_text(encoding="utf-8"))


@router.post("/{slug}/resume/parse")
async def parse_resume(slug: str, file: UploadFile = File(...)):
    import io
    import sys
    import anthropic
    import pdfplumber
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).parent.parent.parent / "core"))
    from config import MODEL, extract_json_object

    content = await file.read()
    filename = file.filename or ""

    if filename.lower().endswith(".pdf"):
        text = ""
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    elif filename.lower().endswith((".docx", ".doc")):
        import docx
        doc = docx.Document(io.BytesIO(content))
        seen = set()
        parts = []

        def add(t: str) -> None:
            t = t.strip()
            if t and t not in seen:
                seen.add(t)
                parts.append(t)

        # Walk document body in order: paragraphs and tables interleaved
        for block in doc.element.body:
            tag = block.tag.split("}")[-1] if "}" in block.tag else block.tag
            if tag == "p":
                from docx.oxml.ns import qn
                runs = block.findall(".//" + qn("w:t"))
                line = "".join(r.text for r in runs if r.text)
                add(line)
            elif tag == "tbl":
                from docx.table import Table as DocxTable
                tbl = DocxTable(block, doc)
                for row in tbl.rows:
                    for cell in row.cells:
                        cell_text = "\n".join(
                            p.text for p in cell.paragraphs if p.text.strip()
                        )
                        add(cell_text)

        text = "\n\n".join(parts)
    else:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are supported")

    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file")

    client = anthropic.Anthropic()

    schema_example = _Path(__file__).parent.parent.parent / "data" / "resume_data.json"
    schema_hint = ""
    if schema_example.exists():
        schema_hint = f"\n\nThe output JSON must follow this exact structure:\n{schema_example.read_text(encoding='utf-8')[:3000]}"

    prompt = f"""Extract structured resume data from the text below.
Return ONLY a valid JSON object matching the resume_data.json schema.
Do not invent information. Use only what is present in the resume text.
{schema_hint}

RESUME TEXT:
{text[:6000]}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )

    parsed = json.loads(extract_json_object(response.content[0].text))
    _PARSE_CACHE[slug] = parsed
    return parsed


@router.post("/{slug}/resume/confirm")
def confirm_resume(slug: str):
    if slug not in _PARSE_CACHE:
        raise HTTPException(status_code=404, detail="No pending parse result for this profile. Run /parse first.")
    parsed = _PARSE_CACHE.pop(slug)
    profile_dir = _profiles_dir() / slug
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "resume_data.json").write_text(
        json.dumps(parsed, indent=2), encoding="utf-8"
    )
    return {"saved": True, "profile": slug}
