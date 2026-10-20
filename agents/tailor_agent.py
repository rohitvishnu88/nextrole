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
from typing import List, Optional, Tuple
from pathlib import Path

import anthropic
from tavily import TavilyClient

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "core"))
from config import MODEL as DEFAULT_MODEL, HUMANISE_RULES, extract_json_object
import resume_builder as _resume_builder
from ats_check import check_ats, extract_pdf_text
from fabrication import find_fabrications

sys.path.insert(0, str(Path(__file__).parent))
import job_analysis

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


def fetch_job_description_with_source(url: str) -> Tuple[str, str]:
    """Return (text, source). source is "page" for the ad itself, "search" for the
    search-snippet fallback (often a different page), or "" when nothing was found."""
    print(f"  Fetching job description from: {url[:70]}...")

    if "linkedin.com/jobs" in url:
        content = _fetch_with_playwright(url)
        if content:
            return content, "page"

    tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    try:
        result = tavily.extract(urls=[url])
        if result.get("results"):
            content = result["results"][0].get("raw_content", "")
            if content:
                return content[:20000], "page"
    except Exception as e:
        print(f"  ⚠️  Tavily extract failed ({e}), falling back to search...")

    try:
        results = tavily.search(query=url, max_results=1, search_depth="basic")
        hits = results.get("results", [])
        if hits:
            return hits[0].get("content", "")[:20000], "search"
    except Exception as e:
        print(f"  ⚠️  Search fallback failed: {e}")

    return "", ""


def fetch_job_description(url: str) -> str:
    return fetch_job_description_with_source(url)[0]


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
            return content[:20000] if content else ""
    except Exception as e:
        print(f"  ⚠️  Playwright fetch failed: {e}")
        return ""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


TAILOR_RULES = """Tailor my resume for this job.

You may:
- reorder bullets so the relevant ones come first
- change wording so my real work is described in their language
- expand a bullet that matters here and shrink one that does not
- adjust my summary and skills list to match what this job is about

You may not:
- add new claims, bigger scope, or titles I did not hold
- stuff in keywords, or list a skill I could not be tested on

At the end, list every change you made and mark the ones I need to confirm are accurate."""


def _targets(analysis: Optional[dict]) -> str:
    if not analysis:
        return ""
    reqs = [r.get("text", "") for r in analysis.get("requirements", [])
            if r.get("filter_likelihood") in ("high", "medium")]
    lines = ["", "The requirements most likely to be real filters for this job:"]
    lines += [f"- {r}" for r in reqs if r]
    if analysis.get("search_terms"):
        lines.append("Exact terms from the ad: " + ", ".join(analysis["search_terms"]))
    return "\n".join(lines)


def tailor_resume(client: anthropic.Anthropic, resume: dict, jd_text: str, analysis: Optional[dict] = None) -> dict:
    prompt = f"""You are an expert resume writer.

{TAILOR_RULES}
{_targets(analysis)}
{HUMANISE_RULES}

JOB DESCRIPTION:
{jd_text}

CURRENT RESUME:
{json.dumps(resume, indent=2)}

Do not change: name, designation, email, phone, job titles, companies, dates, education, certifications.

Return ONLY a JSON object with two fields:
- "resume": the full tailored resume using the exact same structure as the input
- "changes": a list of every change, each {{"location": "summary" | "skills" | "experience[i].description[j]",
  "kind": "reordered" | "reworded" | "expanded" | "shrunk" | "summary" | "skills",
  "before": "original text", "after": "new text", "needs_confirmation": true or false, "reason": "why"}}.
  Use the index of the bullet in the tailored resume for "location"."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )

    parsed = json.loads(extract_json_object(response.content[0].text))
    if "resume" not in parsed:
        return {"resume": parsed, "changes": []}
    changes = parsed.get("changes") if isinstance(parsed.get("changes"), list) else []
    return {"resume": parsed["resume"], "changes": [c for c in changes if isinstance(c, dict)]}


_BULLET_RE = re.compile(r"^experience\[(\d+)\]\.description\[(\d+)\]$")


def _text_at(resume: dict, location: str) -> Optional[str]:
    if location == "summary":
        return resume.get("summary")
    if location == "skills":
        groups = resume.get("skills") or {}
        values = groups.values() if isinstance(groups, dict) else [groups]
        return ", ".join(s for group in values for s in (group if isinstance(group, list) else [group]) if isinstance(s, str))
    match = _BULLET_RE.match(location or "")
    if not match:
        return None
    i, j = int(match.group(1)), int(match.group(2))
    experience = resume.get("experience") or []
    if i >= len(experience):
        return None
    bullets = experience[i].get("description") or []
    return bullets[j] if j < len(bullets) else None


def realign_changes(changes: List[dict], final_resume: dict) -> List[dict]:
    """Point each change's `after` at the final (post-humanise) wording, so the log matches the PDF."""
    realigned = []
    for change in changes:
        change = dict(change)
        final_text = _text_at(final_resume, change.get("location", ""))
        if final_text is None:
            change["stale"] = True
        else:
            change["after"] = final_text
        realigned.append(change)
    return realigned


def ats_terms(analysis: Optional[dict]) -> List[str]:
    if not analysis:
        return []
    terms = list(analysis.get("search_terms") or [])
    for req in analysis.get("requirements") or []:
        if req.get("filter_likelihood") == "high":
            terms += req.get("key_terms") or []
    return terms


def recheck_fit(json_file: str, pdf_file: str, base_file: str, fit_file: str) -> dict:
    """Re-run the deterministic checks after a hand edit; the change log is left as it was."""
    tailored = json.loads(Path(json_file).read_text(encoding="utf-8"))
    base = json.loads(Path(base_file).read_text(encoding="utf-8"))
    fit = json.loads(Path(fit_file).read_text(encoding="utf-8"))
    fit["fabrication_flags"] = find_fabrications(base, tailored)
    fit["ats"] = check_ats(extract_pdf_text(pdf_file), fit.get("ats_terms") or [])
    Path(fit_file).write_text(json.dumps(fit, indent=2), encoding="utf-8")
    return fit


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
    jd_source = "page"
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
        jd_text, jd_source = fetch_job_description_with_source(job_url)
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

    # Step 1: Analyse the job (cached). A job ad too short to analyse still gets tailored.
    print("  Analysing job...")
    # The analysis is advice: if it can't run (search snippet only, too little text, bad
    # model output), tailoring carries on without it.
    analysis = None
    if jd_source == "search":
        print("  ⚠️  Only a search snippet was found, skipping job analysis.")
    else:
        try:
            analysis = job_analysis.get_or_create_analysis(client, profile_slug, resume, jd_text, job_url or None) \
                if profile_slug else job_analysis.analyse_job(client, resume, jd_text, job_url or None)
        except Exception as e:
            print(f"  ⚠️  Job analysis unavailable ({e}), tailoring without it.")

    # Step 2: Tailor resume
    print("  Tailoring resume...")
    tailoring = tailor_resume(client, resume, jd_text, analysis)
    tailored = tailoring["resume"]

    # Step 3: Humanise the resume summary and all bullets (single batched call)
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

    changes = realign_changes(tailoring["changes"], tailored)

    # Step 4: Generate cover letter
    print("  Generating cover letter...")
    cover_letter = generate_cover_letter(client, tailored, jd_text)

    # Step 5: Humanise cover letter
    print("  Humanising cover letter...")
    cover_letter = humanise_pass(client, cover_letter)

    # Save resume JSON and PDF
    json_out = resumes_dir / f"resume_data_{url_slug}.json"
    html_out = resumes_dir / f"resume_{url_slug}.html"
    pdf_out = resumes_dir / f"resume_{url_slug}.pdf"
    meta_out = resumes_dir / f"meta_{url_slug}.json"
    base_out = resumes_dir / f"base_{url_slug}.json"
    fit_out = resumes_dir / f"fit_{url_slug}.json"
    cover_letter_txt = cover_letters_dir / f"cover_letter_{url_slug}.txt"

    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(tailored, f, indent=2)
    print(f"  ✅ Tailored JSON: {json_out.name}")

    # Sidecar metadata so past runs can be listed later - the job_url isn't
    # part of the tailored resume itself, and the in-memory job dict in
    # tailor_api.py doesn't survive a server restart.
    with open(meta_out, "w", encoding="utf-8") as f:
        json.dump({
            "job_url": job_url,
            "created_at": datetime.now().astimezone().isoformat(),
            "analysis_id": analysis["analysis_id"] if analysis else None,
        }, f, indent=2)

    _resume_builder.render_resume(tailored, str(html_out), str(pdf_out))

    # Truthfulness and ATS checks run on the final PDF, against the base resume this run used.
    with open(base_out, "w", encoding="utf-8") as f:
        json.dump(resume, f, indent=2)
    terms = ats_terms(analysis)
    fit = {
        "analysis_id": analysis["analysis_id"] if analysis else None,
        "changes": changes,
        "fabrication_flags": find_fabrications(resume, tailored),
        "ats": check_ats(extract_pdf_text(str(pdf_out)), terms),
        "ats_terms": terms,
    }
    with open(fit_out, "w", encoding="utf-8") as f:
        json.dump(fit, f, indent=2)

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
        "fit_file": str(fit_out),
        "base_file": str(base_out),
        "analysis_id": analysis["analysis_id"] if analysis else None,
    }
