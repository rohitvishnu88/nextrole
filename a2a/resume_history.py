import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

MAX_HISTORY_VERSIONS = 20


def _profiles_dir() -> Path:
    base = os.environ.get("PROFILES_DIR", str(Path(__file__).parent.parent / "data" / "profiles"))
    return Path(base)


def _resume_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_data.json"


def _history_file(slug: str) -> Path:
    return _profiles_dir() / slug / "resume_history.json"


def load_current(slug: str) -> Optional[dict]:
    f = _resume_file(slug)
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def save_current(slug: str, data: dict) -> None:
    f = _resume_file(slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_history(slug: str) -> List[dict]:
    f = _history_file(slug)
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("versions", [])


def save_history(slug: str, versions: List[dict]) -> None:
    f = _history_file(slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"versions": versions}, indent=2), encoding="utf-8")


def push_version(slug: str, change_summary: str) -> None:
    """Snapshot the CURRENT resume_data.json into history before it is overwritten.
    No-op if there is no current resume yet — nothing to snapshot."""
    current = load_current(slug)
    if current is None:
        return
    versions = load_history(slug)
    versions.append({
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "change_summary": change_summary,
        "data": current,
    })
    versions = versions[-MAX_HISTORY_VERSIONS:]
    save_history(slug, versions)


def get_version(slug: str, version_id: str) -> Optional[dict]:
    for v in load_history(slug):
        if v["id"] == version_id:
            return v
    return None


def restore_version(slug: str, version_id: str) -> Optional[dict]:
    """Push the current state to history, then make the given past version current.
    Returns the restored data, or None if version_id doesn't exist."""
    version = get_version(slug, version_id)
    if version is None:
        return None
    push_version(slug, f"Restored version from {version['timestamp']}")
    save_current(slug, version["data"])
    return version["data"]
