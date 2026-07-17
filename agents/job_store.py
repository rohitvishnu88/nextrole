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


def merge_job(store: dict, candidate: dict, now_iso: str) -> None:
    jobs = store.setdefault("jobs", {})
    job_id = make_job_id(candidate["url"])
    existing = jobs.get(job_id)
    if existing is None:
        jobs[job_id] = {
            "id": job_id,
            "source": candidate["source"],
            "title": candidate["title"],
            "company": candidate["company"],
            "location": candidate.get("location", ""),
            "url": candidate["url"],
            "relevance_score": candidate.get("relevance_score", 0),
            "match_reason": candidate.get("match_reason", ""),
            "status": "new",
            "first_seen_at": now_iso,
            "last_seen_at": now_iso,
            "last_verified_at": now_iso,
        }
        return
    existing["last_seen_at"] = now_iso
    if existing["status"] in ("new", "seen"):
        existing["relevance_score"] = candidate.get("relevance_score", existing["relevance_score"])
        existing["match_reason"] = candidate.get("match_reason", existing["match_reason"])


def mark_status(store: dict, job_id: str, status: str) -> bool:
    job = store.get("jobs", {}).get(job_id)
    if job is None:
        return False
    job["status"] = status
    return True


def mark_new_as_seen(store: dict) -> bool:
    changed = False
    for job in store.get("jobs", {}).values():
        if job.get("status") == "new":
            job["status"] = "seen"
            changed = True
    return changed


def visible_jobs(store: dict) -> list:
    jobs = [j for j in store.get("jobs", {}).values() if j.get("status") not in ("dismissed", "closed")]
    return sorted(jobs, key=lambda j: j.get("relevance_score", 0), reverse=True)


def process_search_results(raw_jobs: list, store: dict, now_iso: str, verify_open) -> None:
    tagged = []
    for raw in raw_jobs:
        job = dict(raw)
        job["source"] = derive_source(job.get("url", ""))
        if job["source"] == "other":
            continue
        if not all(job.get(k) for k in ("title", "company", "url")):
            continue
        tagged.append(job)

    non_yc = [j for j in tagged if j["source"] != "yc"]
    yc = [j for j in tagged if j["source"] == "yc"]

    kept = list(non_yc)
    for job in yc:
        combined = dict(store.get("jobs", {}))
        combined.update({f"_pending_{i}": j for i, j in enumerate(kept)})
        if is_cross_source_duplicate(job, combined):
            continue
        kept.append(job)

    for job in kept:
        if verify_open(job["url"]):
            merge_job(store, job, now_iso)
