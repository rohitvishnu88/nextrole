#!/usr/bin/env python3
"""
Main Orchestrator Agent
Runs job search and LinkedIn profile comparison sub-agents.

Usage:
  python3 main_agent.py                    # run both agents
  python3 main_agent.py --jobs-only        # job search only
  python3 main_agent.py --linkedin-only    # LinkedIn comparison only
  python3 main_agent.py --include-seen     # include previously seen jobs
  python3 main_agent.py --applied <url>    # mark a job as applied
  python3 main_agent.py --tailor <url>     # tailor resume to a specific job
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import job_search_agent
import linkedin_agent
import tailor_agent

ROOT = Path(__file__).parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"


def check_env():
    missing = [k for k in ("ANTHROPIC_API_KEY", "TAVILY_API_KEY") if not os.environ.get(k)]
    if missing:
        for k in missing:
            print(f"❌ Missing env var: {k}")
        sys.exit(1)


def load_resume(path=None) -> dict:
    target = path or RESUME_FILE
    if not target.exists():
        print(f"❌ Resume file not found: {target}")
        sys.exit(1)
    with open(target, encoding="utf-8") as f:
        return json.load(f)


def print_jobs(result: dict) -> None:
    jobs = result.get("jobs", [])
    new_count = result.get("new_jobs", len(jobs))

    if not jobs:
        print("  No new jobs found this run.")
        return

    print(f"\n  Found {len(jobs)} job(s) ({new_count} new):\n")
    for i, job in enumerate(jobs, 1):
        score = job.get("relevance_score", "?")
        print(f"  {i}. [{score}/10] {job['title']} at {job['company']} ({job['location']})")
        print(f"       {job.get('match_reason', '')}")
        print(f"       {job.get('url', '')}")
        print()


def print_linkedin(result: dict) -> None:
    if result.get("status") == "skipped":
        print(f"  ⚠️  Skipped: {result['reason']}")
        return

    updates = result.get("updates", {})
    gaps = updates.get("gaps_identified", [])
    missing_skills = updates.get("missing_skills", [])
    missing_certs = updates.get("missing_certifications", [])
    position_updates = updates.get("position_updates", [])

    print(f"\n  Gaps identified: {len(gaps)}")
    for g in gaps:
        print(f"    • {g}")

    if missing_skills:
        print(f"\n  Missing skills on LinkedIn ({len(missing_skills)}):")
        print(f"    {', '.join(missing_skills)}")

    if missing_certs:
        print(f"\n  Missing certifications ({len(missing_certs)}):")
        for c in missing_certs:
            print(f"    • {c}")

    headline = updates.get("headline", {})
    if headline.get("suggested"):
        print(f"\n  Headline update:")
        print(f"    Current:   {headline.get('current', '(empty)')}")
        print(f"    Suggested: {headline['suggested']}")

    print(f"\n  Full suggestions saved to linkedin_updates.json")
    print(f"  {len(position_updates)} position description(s) to update")


def main():
    parser = argparse.ArgumentParser(description="Job search + LinkedIn profile agent")
    parser.add_argument("--jobs-only", action="store_true", help="Run job search only")
    parser.add_argument("--linkedin-only", action="store_true", help="Run LinkedIn comparison only")
    parser.add_argument("--include-seen", action="store_true", help="Include previously seen jobs")
    parser.add_argument("--applied", metavar="URL", help="Mark a job URL as applied")
    parser.add_argument("--tailor", metavar="URL", help="Tailor resume to a specific job URL")
    parser.add_argument("--tailor-jd", metavar="FILE", help="Tailor resume to a pasted JD text file in data/")
    parser.add_argument("--profile", metavar="SLUG", default="", help="Profile slug (required if multiple profiles exist)")
    args = parser.parse_args()

    def _resolve_profile() -> str:
        profiles_json = ROOT / "data" / "profiles" / "profiles.json"
        if not profiles_json.exists():
            return args.profile
        import json as _json
        profiles_list = _json.loads(profiles_json.read_text())
        if len(profiles_list) > 1 and not args.profile:
            names = ", ".join(p["slug"] for p in profiles_list)
            print(f"❌ Multiple profiles exist. Specify one with --profile. Available: {names}")
            sys.exit(1)
        return args.profile or (profiles_list[0]["slug"] if profiles_list else "")

    check_env()
    profile_slug = _resolve_profile()

    # Handle --applied flag
    if args.applied:
        job_search_agent.mark_applied(args.applied)
        return

    # Handle --tailor flag
    if args.tailor:
        print(f"\n{'='*55}")
        print(f"  Tailoring resume to job")
        print(f"{'='*55}\n")
        result = tailor_agent.run(job_url=args.tailor, profile_slug=profile_slug)
        if result["status"] == "completed":
            print(f"\n  ✅ Tailored resume ready:")
            print(f"     JSON: {result['json_file']}")
            print(f"     PDF:  {result['pdf_file']}")
            print(f"     Cover letter: {result['cover_letter_file']}")
        else:
            print(f"\n  ❌ Failed: {result.get('reason')}")
        return

    # Handle --tailor-jd flag
    if args.tailor_jd:
        print(f"\n{'='*55}")
        print(f"  Tailoring resume to JD: {args.tailor_jd}")
        print(f"{'='*55}\n")
        result = tailor_agent.run(jd_file=args.tailor_jd, profile_slug=profile_slug)
        if result["status"] == "completed":
            print(f"\n  ✅ Tailored resume ready:")
            print(f"     JSON: {result['json_file']}")
            print(f"     PDF:  {result['pdf_file']}")
            print(f"     Cover letter: {result['cover_letter_file']}")
        else:
            print(f"\n  ❌ Failed: {result.get('reason')}")
        return

    if profile_slug:
        resume_path = ROOT / "data" / "profiles" / profile_slug / "resume_data.json"
    else:
        resume_path = RESUME_FILE
    resume = load_resume(resume_path)
    run_jobs = not args.linkedin_only
    run_linkedin = not args.jobs_only

    print(f"\n{'='*55}")
    print(f"  Agent starting for: {resume.get('name', '')}")
    print(f"{'='*55}\n")

    # Job search sub-agent
    if run_jobs:
        print("[ Job Search Agent ]")
        jobs_result = job_search_agent.run(resume, include_seen=args.include_seen, profile_slug=profile_slug)
        print_jobs(jobs_result)
        print(f"  Results saved to jobs.json")

    # LinkedIn sub-agent
    if run_linkedin:
        print("[ LinkedIn Profile Agent ]")
        linkedin_result = linkedin_agent.run(resume)
        print_linkedin(linkedin_result)

    print(f"\n{'='*55}")
    print("  Done.")
    print(f"{'='*55}\n")

    if run_jobs and args.applied is None:
        print("  Tip: mark a job as applied with:")
        print("  python3 main_agent.py --applied <linkedin-url>\n")


if __name__ == "__main__":
    main()
