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
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
from tavily import TavilyClient

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from config import MODEL as DEFAULT_MODEL, extract_json_array

ROOT = Path(__file__).parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"
JOBS_FILE = ROOT / "output" / "jobs" / "jobs.json"
SEEN_FILE = ROOT / "output" / "jobs" / "seen_jobs.json"
APPLIED_FILE = ROOT / "output" / "jobs" / "applied_jobs.json"
MODEL = DEFAULT_MODEL
MAX_RESULTS_PER_QUERY = 5
# LinkedIn date filter param: r432000 = past 5 days
LINKEDIN_DATE_FILTER = "f_TPR=r432000"


def load_json(path, default):
    if Path(path).exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


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
- LinkedIn jobs only."""

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

    body_lines = [f"<h2>{len(jobs)} new LinkedIn jobs matched your profile</h2><br>"]
    for i, job in enumerate(jobs, 1):
        score = job.get("relevance_score", "?")
        body_lines.append(
            f"<b>{i}. [{score}/10] {job['title']}</b> at {job['company']} ({job['location']})<br>"
            f"{job.get('match_reason', '')}<br>"
            f"<a href='{job.get('url', '')}'>View on LinkedIn</a><br><br>"
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


def run(resume: dict, include_seen: bool = False, profile_slug: str = "") -> dict:
    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

    seen_urls: set = set(load_json(SEEN_FILE, []))
    applied_urls: set = set(load_json(APPLIED_FILE, []))
    profile = build_profile_summary(resume, profile_slug)

    tools = [
        {
            "name": "search_linkedin_jobs",
            "description": (
                "Search LinkedIn for job listings. Returns title, company, location, URL, snippet."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query including site:linkedin.com/jobs"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "read_job_page",
            "description": (
                "Fetch the full content of a LinkedIn job listing URL to get the complete "
                "job description before scoring it."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full LinkedIn job URL"
                    }
                },
                "required": ["url"]
            }
        }
    ]

    system_prompt = """You are a job search agent. Find LinkedIn jobs posted in the last 5 days that match the candidate's profile.

Process:
1. Run exactly 10 searches — no more. Mix role titles and skill angles:
   a. Direct listing: site:linkedin.com/jobs/view <role> <skills> UK
   b. Search page: site:linkedin.com/jobs/search keywords=<role> location=UK f_TPR=r432000
2. Role angles to cover: Solution Architect, Integration Architect, API Architect, Data Architect, Senior/Lead/Principal Data Engineer, Data Platform Engineer.
3. Skill angles to cover: MuleSoft, Apigee, Kafka, Apache Iceberg, Databricks, Snowflake, AWS data platform, Azure data platform, event-driven architecture, API management.
4. After 10 searches, stop searching. Read the top 8 job pages then score everything.
5. Only include jobs from linkedin.com — discard any other domains.
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
- Any domain other than linkedin.com
- Pure front-end, DevOps-only, or QA-only roles with no architecture/data/integration component

Return ONLY a JSON array, no other text:
[
  {
    "title": "Job title",
    "company": "Company name",
    "location": "Location",
    "url": "LinkedIn URL",
    "relevance_score": 8,
    "match_reason": "One sentence on why this fits — mention specific matching skills or experience"
  }
]"""

    messages = [
        {
            "role": "user",
            "content": f"Find relevant LinkedIn jobs for this candidate:\n\n{profile}"
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

    while True:
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

                if block.name == "search_linkedin_jobs":
                    query = block.input["query"]
                    print(f"  Searching: {query}")
                    try:
                        results = tavily_client.search(
                            query=query,
                            max_results=MAX_RESULTS_PER_QUERY,
                            search_depth="advanced",
                            include_domains=["linkedin.com"],
                        )
                        hits = results.get("results", [])
                        # Hard filter: LinkedIn jobs only
                        hits = [
                            r for r in hits
                            if "linkedin.com/jobs" in r.get("url", "")
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
                    url = block.input["url"]
                    print(f"  Reading full page: {url[:60]}...")
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

    # Filter applied jobs
    all_jobs = [j for j in all_jobs if j.get("url") not in applied_urls]

    # Split into new vs previously seen
    new_jobs = [j for j in all_jobs if j.get("url") not in seen_urls]
    old_jobs = [j for j in all_jobs if j.get("url") in seen_urls] if include_seen else []

    # Update seen list
    for job in all_jobs:
        if job.get("url"):
            seen_urls.add(job["url"])
    save_json(SEEN_FILE, list(seen_urls))

    # Send email for new jobs
    if new_jobs:
        candidate_name = resume.get("name", "Candidate")
        print(f"  Sending email for {len(new_jobs)} new job(s)...")
        try:
            send_email(new_jobs, candidate_name)
        except Exception as e:
            print(f"  ⚠️  Email failed: {e}")

    jobs_sorted = sorted(all_jobs if include_seen else new_jobs,
                         key=lambda x: x.get("relevance_score", 0), reverse=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "candidate": resume.get("name", ""),
        "total_jobs": len(jobs_sorted),
        "new_jobs": len(new_jobs),
        "jobs": jobs_sorted,
    }

    save_json(JOBS_FILE, output)
    return output


def mark_applied(url: str) -> None:
    applied = set(load_json(APPLIED_FILE, []))
    applied.add(url)
    save_json(APPLIED_FILE, list(applied))
    print(f"✅ Marked as applied: {url}")
