"""Persistent per-profile job-match store: paths, merge, dedup, status, feedback summary."""
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent


def _output_dir() -> Path:
    base = os.environ.get("JOBS_OUTPUT_DIR", str(ROOT / "output"))
    return Path(base)


def profile_jobs_path(profile_slug: str) -> Path:
    if not profile_slug:
        return _output_dir() / "jobs" / "jobs.json"
    if not re.match(r"^[a-z0-9-]+$", profile_slug):
        raise ValueError(f"invalid profile_slug: {profile_slug!r}")
    return _output_dir() / "profiles" / profile_slug / "jobs.json"


def load_store(profile_slug: str) -> dict:
    path = profile_jobs_path(profile_slug)
    if not path.exists():
        return {"generated_at": "", "candidate": "", "jobs": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {}
    data.setdefault("generated_at", "")
    data.setdefault("candidate", "")
    data.setdefault("jobs", {})
    if not isinstance(data["jobs"], dict):
        data["jobs"] = {}
    return data


def save_store(profile_slug: str, store: dict) -> None:
    path = profile_jobs_path(profile_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2), encoding="utf-8")


def make_job_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def derive_source(url: str) -> str:
    host = urlparse(url).netloc.lower()
    for domain, source in (
        ("greenhouse.io", "greenhouse"),
        ("lever.co", "lever"),
        ("workatastartup.com", "yc"),
        ("linkedin.com", "linkedin"),
    ):
        if host == domain or host.endswith("." + domain):
            return source
    return "other"


def normalize_dedup_key(company: str, title: str) -> str:
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())
    return f"{norm(company)}::{norm(title)}"


def is_cross_source_duplicate(candidate: dict, existing_jobs: dict) -> bool:
    if candidate.get("source") != "yc":
        return False
    key = normalize_dedup_key(candidate.get("company", ""), candidate.get("title", ""))
    for job in existing_jobs.values():
        if job.get("source") == "yc":
            continue
        if normalize_dedup_key(job.get("company", ""), job.get("title", "")) == key:
            return True
    return False
