"""Who owns which profile, and the one check every slug-taking route goes through."""
import json
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException

from a2a import resume_history
from a2a.auth import User

MAX_PROFILES_PER_USER = 3


def profiles_dir() -> Path:
    return Path(os.environ.get("PROFILES_DIR", str(Path(__file__).parent.parent / "data" / "profiles")))


def load_meta() -> List[dict]:
    path = profiles_dir() / "profiles.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_meta(profiles: List[dict]) -> None:
    profiles_dir().mkdir(parents=True, exist_ok=True)
    (profiles_dir() / "profiles.json").write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def owner_of(profile: dict) -> Optional[str]:
    return profile.get("owner_user_id")


def _can_see(profile: dict, user: User) -> bool:
    # Profiles from before sign-in existed have no owner; until assigned they're the owner's.
    owner = owner_of(profile)
    return owner == user.id if owner else user.is_owner


def visible_profiles(user: User) -> List[dict]:
    return [p for p in load_meta() if _can_see(p, user)]


def require_profile(slug: str, user: User) -> dict:
    try:
        resume_history.validate_slug(slug)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid profile slug")
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid profile slug")
    profile = next((p for p in load_meta() if p["slug"] == slug), None)
    if profile is None:
        # A folder with no metadata entry is legacy data: visible to the owner only.
        if (profiles_dir() / slug).is_dir() and user.is_owner:
            return {"slug": slug}
        raise HTTPException(status_code=404, detail="Profile not found")
    if not _can_see(profile, user):
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


def output_profiles_dir() -> Path:
    base = os.environ.get("JOBS_OUTPUT_DIR", str(Path(__file__).parent.parent / "output"))
    return Path(base) / "profiles"


def unique_slug(base: str) -> str:
    base = re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-") or "profile"
    # Anything a previous profile left behind (output files, applications) also counts as
    # taken, so a new profile never inherits someone else's history.
    from a2a import db
    taken = (
        {p["slug"] for p in load_meta()}
        | {d.name for d in profiles_dir().glob("*") if d.is_dir()}
        | {d.name for d in output_profiles_dir().glob("*") if d.is_dir()}
        | db.application_profile_ids()
    )
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def assign_unowned_to(owner_user_id: str) -> int:
    profiles = load_meta()
    count = 0
    for p in profiles:
        if not owner_of(p):
            p["owner_user_id"] = owner_user_id
            count += 1
    if count:
        save_meta(profiles)
    return count
