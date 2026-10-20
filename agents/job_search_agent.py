#!/usr/bin/env python3
"""
Job Search Sub-agent
Searches LinkedIn for jobs matching the candidate's resume via Tavily,
scores results with Claude, tracks seen/applied jobs, and emails new findings.
"""

import json
import os
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
from tavily import TavilyClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.ai_clients import make_anthropic, make_tavily
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL, extract_json_array

sys.path.insert(0, str(Path(__file__).parent))
import job_store
import job_freshness

ROOT = Path(__file__).parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"
MODEL = DEFAULT_MODEL
MAX_RESULTS_PER_QUERY = 20
SEARCH_DOMAINS = ["linkedin.com", "boards.greenhouse.io", "jobs.lever.co", "workatastartup.com"]
MAX_SEARCHES = 16
MAX_PAGE_READS = 8


def build_profile_summary(resume: dict, profile_slug: str = "") -> str:
    name = resume.get("name", "")
    summary = resume.get("summary", "")
    skills_by_group = resume.get("skills", {})
    skills_section = chr(10).join(
        f'  {group}: {", ".join(items)}' for group, items in skills_by_group.items()
    )

    # Use search brief signals when available
    brief_path = ROOT / "data" / "profiles" / profile_slug / "search_brief.json" if profile_slug else None
    if brief_path and brief_path.exists():
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        active = [s for s in brief.get("signals", []) if s.get("active")]

        def sig(cat: str) -> list:
            return [s["label"] for s in active if s["category"] == cat]

        roles      = sig("roles")
        skills     = sig("skills")
        locations  = sig("location")
        industries = sig("industries")
        excludes   = sig("exclusions")
        seniority  = sig("seniority")

        exp = resume.get("experience", [{}])
        current_title   = exp[0].get("title", "") if exp else ""
        current_company = exp[0].get("company", "") if exp else ""

        feedback_summary = job_store.build_feedback_summary(job_store.load_store(profile_slug))

        return f"""Candidate: {name}
Seniority target: {", ".join(seniority) if seniority else "Senior/Principal"}
Current role: {current_title} at {current_company}
Summary: {summary}

Target roles (search for any of these): {", ".join(roles) if roles else "Solution Architect, Senior Data Engineer"}

Core skills to match:
{chr(10).join(f"  - {s}" for s in skills) if skills else skills_section}

Target locations: {", ".join(locations) if locations else "UK only"}
Target industries: {", ".join(industries) if industries else "any industry"}

Hard exclusions (never match):
{chr(10).join(f"  - {e}" for e in excludes) if excludes else "  - Junior, Graduate, Associate, Entry-level"}

Additional context:
{skills_section}

Hard requirements:
- Posted within the last 5 days. Discard anything older.
- Jobs from LinkedIn, Greenhouse, Lever, or workatastartup.com only.
{f"{chr(10)}{feedback_summary}" if feedback_summary else ""}"""

    # Fallback: original hardcoded profile
    titles    = [exp.get("title", "") for exp in resume.get("experience", [])[:3]]
    companies = [exp.get("company", "") for exp in resume.get("experience", [])[:3]]
    certs     = [c.get("name", "") for c in resume.get("certifications", [])]

    return f"""Candidate: {name}
Seniority: Senior/Principal level, 15 years total experience
Current role: {titles[0] if titles else ''} at {companies[0] if companies else ''}
Recent titles: {', '.join(titles)}
Summary: {summary}

Target roles (any of these): Solution Architect, Integration Architect, API Architect, Data Integration Architect, Data Architect, Data Platform Architect, Technical Architect, Enterprise Architect, Senior Data Engineer, Lead Data Engineer, Staff Data Engineer, Principal Data Engineer, Data Platform Engineer, Head of Data Engineering, Engineering Manager (Data/Integration)

Transferable tech (candidate can cover these without significant learning — include roles using these):
- Databricks / Delta Lake (same as PySpark + Iceberg — direct transfer)
- Azure Data Factory, Synapse Analytics (same patterns as AWS Glue + MWAA)
- Azure Event Hubs (same as Kafka)
- dbt (same SQL transformation layer, candidate uses PySpark equivalents)
- Snowflake (certified Snowflake Pro Core)
- Azure API Management, AWS API Gateway (same as Apigee/Kong/MuleSoft)
- IBM App Connect, WSO2, Boomi (same as MuleSoft integration patterns)

Target industries: Financial services, Banking, Automotive, Aviation, Telecoms, Retail — or open to any industry

Location: UK only (London, remote-UK, hybrid-UK). No relocation.

Core skills:
{skills_section}

Certifications: {', '.join(certs)}

Hard requirements for a job to be relevant:
- Senior/Lead/Principal/Architect level only. No junior, mid-level, graduate, or associate roles.
- UK-based or remote-UK. No international relocation.
- Must involve at least 2 of: data engineering, cloud data platforms, API/integration architecture, solution architecture
- Permanent or contract — either fine
- Posted within the last 5 days. Discard anything older."""


def send_email(jobs: list[dict], candidate_name: str) -> None:
    gmail_user = os.environ.get("GMAIL_USER", "rohitvishnu@gmail.com")
    gmail_pass = os.environ.get("GMAIL_APP_PASS")
    if not gmail_pass:
        print("  ⚠️  GMAIL_APP_PASS not set — skipping email")
        return

    subject = f"[Job Agent] {len(jobs)} new job(s) found for {candidate_name}"

    body_lines = [f"<h2>{len(jobs)} new jobs matched your profile</h2><br>"]
    for i, job in enumerate(jobs, 1):
        score = job.get("relevance_score", "?")
        body_lines.append(
            f"<b>{i}. [{score}/10] {job['title']}</b> at {job['company']} ({job['location']})<br>"
            f"{job.get('match_reason', '')}<br>"
            f"<a href='{job.get('url', '')}'>View listing</a><br><br>"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = gmail_user
    msg.attach(MIMEText("\n".join(body_lines), "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, gmail_user, msg.as_string())

    print(f"  ✅ Email sent to {gmail_user}")


def run(resume: dict, include_seen: bool = False, profile_slug: str = "", send_email: bool = True) -> dict:
    anthropic_client = make_anthropic()
    tavily_client = make_tavily()

    profile = build_profile_summary(resume, profile_slug)

    tools = [
        {
            "name": "search_job_boards",
            "description": (
                "Search LinkedIn, Greenhouse, Lever, or Y Combinator's workatastartup.com "
                "for job listings. Returns title, company, location, URL, snippet."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query including a site: filter, e.g. "
                            "'site:boards.greenhouse.io Data Engineer'"
                        )
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "read_job_page",
            "description": (
                "Fetch the full content of a job listing URL to get the complete "
                "job description before scoring it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full job listing URL"
                    }
                },
                "required": ["url"]
            }
        }
    ]

    system_prompt = """You are a job search agent. Find jobs posted in the last 5 days that match the candidate's profile.

Process:
1. Run up to 16 searches across four sources — no more. Mix role titles and skill angles:
   a. site:linkedin.com/jobs/view <role> <skills> UK
   b. site:linkedin.com/jobs/search keywords=<role> location=UK f_TPR=r432000 — a different query
      shape than (a); use this angle too, not just direct listing pages.
   c. site:boards.greenhouse.io <role> <skills>
   d. site:jobs.lever.co <role> <skills>
   e. site:workatastartup.com <role> <skills> — treat this source as SUPPLEMENTARY: only worth
      searching if the other sources haven't already covered a role/skill angle well.
2. Role angles to cover: Solution Architect, Integration Architect, API Architect, Data Architect, Senior/Lead/Principal Data Engineer, Data Platform Engineer.
3. Skill angles to cover: MuleSoft, Apigee, Kafka, Apache Iceberg, Databricks, Snowflake, AWS data platform, Azure data platform, event-driven architecture, API management.
4. After searching, stop. Read the top 8 job pages then score everything.
5. Only include jobs from linkedin.com, boards.greenhouse.io, jobs.lever.co, or workatastartup.com — discard any other domain.
6. Discard any job posted more than 5 days ago.

Scoring rubric (1-10):
- 9-10: Exact fit. Architect or Senior/Lead/Principal Engineer title. Core tech matches (Iceberg, Kafka, MuleSoft, Apigee, AWS, or API management). UK-based.
- 7-8: Strong fit. Right seniority and domain. Transferable tech stack: Databricks, Delta Lake, Azure Data Factory, Synapse, dbt, Snowflake, Azure APIM, AWS API Gateway, IBM App Connect, Boomi. Candidate covers these without significant reskilling.
- 6: Transferable fit. Right level, overlapping domain, different but learnable stack.
- 1-5: Drop.

HARD DISCARD rules — drop immediately without scoring:
- Any title with: Junior, Mid-level, Graduate, Associate, Entry-level, Intern
- Any role outside UK (no US, EU, APAC unless explicitly remote-global)
- Any role posted more than 5 days ago
- Any domain other than linkedin.com, boards.greenhouse.io, jobs.lever.co, workatastartup.com
- Pure front-end, DevOps-only, or QA-only roles with no architecture/data/integration component

Return ONLY a JSON array, no other text:
[
  {
    "title": "Job title",
    "company": "Company name",
    "location": "Location",
    "url": "Job listing URL",
    "relevance_score": 8,
    "match_reason": "One sentence on why this fits — mention specific matching skills or experience",
    "red_flags": ["Explicit blockers stated in the text only, e.g. no visa sponsorship, security clearance required, on-site in a non-UK location. Empty list if none."]
  }
]"""

    messages = [
        {
            "role": "user",
            "content": f"Find relevant jobs for this candidate:\n\n{profile}"
        }
    ]

    print("  Searching for jobs...")

    def call_api(messages):
        for attempt in range(5):
            try:
                return anthropic_client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=system_prompt,
                    tools=tools,
                    messages=messages,
                )
            except anthropic.RateLimitError as e:
                wait = 60
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
                wait = 2 ** attempt
                print(f"  API error ({e.__class__.__name__}), retrying in {wait}s...")
                time.sleep(wait)
        raise RuntimeError("API failed after 5 attempts")

    search_count = 0
    page_read_count = 0
    read_urls = set()
    iterations = 0
    max_iterations = MAX_SEARCHES + MAX_PAGE_READS + 10

    while True:
        iterations += 1
        if iterations > max_iterations:
            print(f"  ⚠️  Tool loop exceeded {max_iterations} iterations, stopping without scoring.")
            all_jobs = []
            break

        response = call_api(messages)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason in ("end_turn", "stop_sequence"):
            all_jobs = []
            for block in response.content:
                if not hasattr(block, "text") or not block.text.strip():
                    continue
                text = extract_json_array(block.text)
                if text:
                    all_jobs = json.loads(text)
                    break
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "search_job_boards":
                    if search_count >= MAX_SEARCHES:
                        tool_output = json.dumps({
                            "error": "Search limit reached. Stop searching and score the jobs found so far."
                        })
                    else:
                        search_count += 1
                        query = block.input["query"]
                        print(f"  Searching ({search_count}/{MAX_SEARCHES}): {query}")
                        try:
                            results = tavily_client.search(
                                query=query,
                                max_results=MAX_RESULTS_PER_QUERY,
                                search_depth="advanced",
                                include_domains=SEARCH_DOMAINS,
                            )
                            hits = results.get("results", [])
                            hits = [
                                r for r in hits
                                if job_store.derive_source(r.get("url", "")) != "other"
                            ]
                            formatted = [
                                {
                                    "title": r.get("title", ""),
                                    "url": r.get("url", ""),
                                    "snippet": r.get("content", "")[:150],
                                }
                                for r in hits
                            ]
                            tool_output = json.dumps(formatted)
                        except Exception as e:
                            tool_output = json.dumps({"error": str(e)})

                elif block.name == "read_job_page":
                    if page_read_count >= MAX_PAGE_READS:
                        tool_output = json.dumps({
                            "error": "Page read limit reached. Score using the data already gathered."
                        })
                    else:
                        page_read_count += 1
                        url = block.input["url"]
                        read_urls.add(url)
                        print(f"  Reading full page ({page_read_count}/{MAX_PAGE_READS}): {url[:60]}...")
                        try:
                            result = tavily_client.extract(urls=[url])
                            content = ""
                            if result.get("results"):
                                content = result["results"][0].get("raw_content", "")[:600]
                            tool_output = json.dumps({"url": url, "content": content or "Could not extract content"})
                        except Exception as e:
                            tool_output = json.dumps({"error": str(e)})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_output,
                })

            messages.append({"role": "user", "content": tool_results})

    store = job_store.load_store(profile_slug)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    ids_before = set(store.get("jobs", {}).keys())
    # Decided in Python, not by the model: only pages the agent actually read count as "full".
    for job in all_jobs:
        job["text_basis"] = "full" if job.get("url") in read_urls else "snippet"
    job_store.process_search_results(
        all_jobs, store, now_iso,
        verify_open=lambda url: job_freshness.verify_open(url, tavily_client),
    )
    job_store.reverify_stale_jobs(
        store, now,
        verify_open=lambda url: job_freshness.verify_open(url, tavily_client),
    )

    newly_added_ids = set(store.get("jobs", {}).keys()) - ids_before
    freshly_new_jobs = [store["jobs"][jid] for jid in newly_added_ids]

    if freshly_new_jobs and send_email:
        candidate_name = resume.get("name", "Candidate")
        print(f"  Sending email for {len(freshly_new_jobs)} new job(s)...")
        try:
            send_email(freshly_new_jobs, candidate_name)
        except Exception as e:
            print(f"  ⚠️  Email failed: {e}")

    job_store.save_store(profile_slug, store)

    visible = job_store.visible_jobs(store)
    jobs_sorted = visible if include_seen else [j for j in visible if j.get("status") == "new"]

    output = {
        "generated_at": now_iso,
        "candidate": resume.get("name", ""),
        "total_jobs": len(jobs_sorted),
        "new_jobs": len([j for j in visible if j.get("status") == "new"]),
        "jobs": jobs_sorted,
    }
    return output


def mark_applied(url: str, profile_slug: str = "") -> bool:
    store = job_store.load_store(profile_slug)
    job_id = job_store.make_job_id(url)
    ok = job_store.mark_status(store, job_id, "applied")
    if ok:
        job_store.save_store(profile_slug, store)
        print(f"✅ Marked as applied: {url}")
    else:
        print(f"⚠️  URL not found in job store, nothing to mark: {url}")
    return ok
