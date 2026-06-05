#!/usr/bin/env python3
"""
Resume Tailoring Sub-agent
Fetches a job description, tailors the resume, generates a cover letter,
and applies humanise rules to both before producing PDFs.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from tavily import TavilyClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))
from config import MODEL as DEFAULT_MODEL, HUMANISE_RULES, extract_json_object
import resume_builder as _resume_builder

RESUME_FILE = ROOT / "data" / "resume_data.json"
RESUMES_DIR = ROOT / "output" / "resumes"
COVER_LETTERS_DIR = ROOT / "output" / "cover_letters"
MODEL = DEFAULT_MODEL


def load_resume(profile_slug: str = "") -> dict:
    if profile_slug:
        path = ROOT / "data" / "profiles" / profile_slug / "resume_data.json"
    else:
        path = RESUME_FILE
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_job_description(url: str) -> str:
    print(f"  Fetching job description from: {url[:70]}...")

    if "linkedin.com/jobs" in url:
        content = _fetch_with_playwright(url)
        if content:
            return content

    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    try:
        result = tavily.extract(urls=[url])
        if result.get("results"):
            content = result["results"][0].get("raw_content", "")
            if content:
                return content[:4000]
    except Exception as e:
        print(f"  ⚠️  Tavily extract failed ({e}), falling back to search...")

    try:
        results = tavily.search(query=url, max_results=1, search_depth="basic")
        hits = results.get("results", [])
        if hits:
            return hits[0].get("content", "")[:4000]
    except Exception as e:
        print(f"  ⚠️  Search fallback failed: {e}")

    return ""


def _fetch_with_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)

            content = ""
            for selector in [".description__text", ".job-view-layout", ".jobs-description", "main"]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        content = el.inner_text()
                        if len(content) > 200:
                            break
                except Exception:
                    continue

            browser.close()
            return content[:4000] if content else ""
    except Exception as e:
        print(f"  ⚠️  Playwright fetch failed: {e}")
        return ""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def tailor_resume(client: anthropic.Anthropic, resume: dict, jd_text: str) -> dict:
    prompt = f"""You are an expert resume writer. Tailor this resume to match the job description below.

Rules:
- Keep all facts accurate. Do not invent experience, skills, or achievements.
- Rewrite the summary to speak directly to this role.
- Reorder bullet points so the most relevant ones come first in each job.
- Emphasise skills and tools mentioned in the JD that the candidate already has.
- Remove or deprioritise bullets irrelevant to this role.
{HUMANISE_RULES}

JOB DESCRIPTION:
{jd_text}

CURRENT RESUME:
{json.dumps(resume, indent=2)}

Return the full tailored resume as a JSON object using the exact same structure as the input.
Only change: summary, experience descriptions (reorder + rewrite bullets), skill group ordering.
Do not change: name, email, phone, job titles, companies, dates, education, certifications.
Return ONLY the JSON object, no other text."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = extract_json_object(response.content[0].text)
    return json.loads(text)


def generate_cover_letter(client: anthropic.Anthropic, resume: dict, jd_text: str) -> str:
    prompt = f"""Write a cover letter for this candidate applying to the job below.

{HUMANISE_RULES}

Additional cover letter rules:
- Do NOT start with "I am writing to apply" or "I am excited" or "Dear Hiring Manager,".
- Open with something specific about the role or company that shows you read the JD.
- 3-4 short paragraphs max. Under 300 words total.
- First paragraph: why this specific role at this specific company.
- Second paragraph: one or two concrete things from the candidate's background that directly match.
- Third paragraph: what you'd bring on day one. Be specific, not vague.
- No closing fluff: no "I look forward to hearing from you", no "Thank you for your consideration".
- End on something direct and confident.
- Do not mention "cover letter" anywhere in the text.
- Use first person throughout.
- Write like a senior consultant who has done this before, not like someone desperate for a job.

CANDIDATE PROFILE:
Name: {resume.get("name")}
Current role: {resume["experience"][0]["title"]} at {resume["experience"][0]["company"]}
Summary: {resume.get("summary")}

JOB DESCRIPTION:
{jd_text}

Return only the cover letter text. No subject line, no date, no address header."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def humanise_pass(client: anthropic.Anthropic, text: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": f"You are a writing editor. Remove all signs of AI-generated writing.\n\n{HUMANISE_RULES}",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{
            "role": "user",
            "content": f"Rewrite the text below applying all rules. Return only the final humanised text, no commentary.\n\nTEXT:\n{text}",
        }],
    )
    return response.content[0].text.strip()


def humanise_bullets_batch(client: anthropic.Anthropic, bullets: list[str]) -> list[str]:
    if not bullets:
        return bullets

    numbered = "\n".join(f"{i+1}. {b}" for i, b in enumerate(bullets))
    response = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        system=[
            {
                "type": "text",
                "text": f"You are a writing editor. Remove all signs of AI-generated writing.\n\n{HUMANISE_RULES}",
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{
            "role": "user",
            "content": (
                "Rewrite each numbered bullet below applying all rules. "
                "Return ONLY the numbered list in the same format — one bullet per line, same count. No commentary.\n\n"
                f"BULLETS:\n{numbered}"
            ),
        }],
    )

    text = response.content[0].text.strip()
    lines = [re.sub(r"^\d+\.\s*", "", ln).strip() for ln in text.splitlines() if ln.strip()]

    if len(lines) != len(bullets):
        print(f"  ⚠️  Batch humanise count mismatch ({len(lines)} vs {len(bullets)}), falling back to originals")
        return bullets

    return lines


def run(job_url: str = "", jd_file: str = "", jd_text: str = "", profile_slug: str = "") -> dict:
    resume = load_resume(profile_slug)
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Get JD text from raw text, file, or URL
    if jd_text:
        source_slug = "jd_text"
    elif jd_file:
        jd_path = Path(jd_file)
        if not jd_path.exists():
            # Try relative to data dir
            jd_path = ROOT / "data" / jd_file
        if not jd_path.exists():
            return {"status": "error", "reason": f"JD file not found: {jd_file}"}
        jd_text = jd_path.read_text(encoding="utf-8")
        source_slug = slugify(jd_path.stem)
    else:
        jd_text = fetch_job_description(job_url)
        if not jd_text:
            return {"status": "error", "reason": "Could not fetch job description from URL."}
        source_slug = slugify(job_url.split("/")[-1] or job_url.split("/")[-2])

    # Unique slug: source + timestamp so every run is preserved
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    profile_prefix = f"{profile_slug}_" if profile_slug else ""
    url_slug = f"{profile_prefix}{source_slug}_{timestamp}"

    if profile_slug:
        resumes_dir = ROOT / "output" / "profiles" / profile_slug / "resumes"
        cover_letters_dir = ROOT / "output" / "profiles" / profile_slug / "cover_letters"
    else:
        resumes_dir = RESUMES_DIR
        cover_letters_dir = COVER_LETTERS_DIR

    resumes_dir.mkdir(parents=True, exist_ok=True)
    cover_letters_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Tailor resume
    print("  Tailoring resume...")
    tailored = tailor_resume(client, resume, jd_text)

    # Step 2: Humanise the resume summary and all bullets (single batched call)
    print("  Humanising resume...")
    tailored["summary"] = humanise_pass(client, tailored.get("summary", ""))

    all_bullets = []
    bullet_index = []
    for i, exp in enumerate(tailored.get("experience", [])):
        for j, bullet in enumerate(exp.get("description", [])):
            all_bullets.append(bullet)
            bullet_index.append((i, j))

    if all_bullets:
        humanised = humanise_bullets_batch(client, all_bullets)
        for (i, j), h in zip(bullet_index, humanised):
            tailored["experience"][i]["description"][j] = h

    # Step 3: Generate cover letter
    print("  Generating cover letter...")
    cover_letter = generate_cover_letter(client, tailored, jd_text)

    # Step 4: Humanise cover letter
    print("  Humanising cover letter...")
    cover_letter = humanise_pass(client, cover_letter)

    # Save resume JSON and PDF
    json_out = resumes_dir / f"resume_data_{url_slug}.json"
    html_out = resumes_dir / f"resume_{url_slug}.html"
    pdf_out = resumes_dir / f"resume_{url_slug}.pdf"
    cover_letter_txt = cover_letters_dir / f"cover_letter_{url_slug}.txt"

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(tailored, f, indent=2)
    print(f"  ✅ Tailored JSON: {json_out.name}")

    _resume_builder.render_resume(tailored, str(html_out), str(pdf_out))

    # Save cover letter
    with open(cover_letter_txt, "w", encoding="utf-8") as f:
        f.write(cover_letter)
    print(f"  ✅ Cover letter: {cover_letter_txt.name}")

    print("\n  Summary:")
    print(f"  {tailored['summary'][:200]}...")
    print(f"\n  Cover letter preview:")
    print(f"  {cover_letter[:300]}...")

    return {
        "status": "completed",
        "job_url": job_url,
        "json_file": str(json_out),
        "pdf_file": str(pdf_out),
        "cover_letter_file": str(cover_letter_txt),
    }
