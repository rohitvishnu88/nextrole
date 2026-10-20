"""What an applicant tracking system can read from a rendered resume PDF."""
import re
from typing import List

import pdfplumber

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s()-]{8,}\d")
# Each heading and the labels resume templates commonly use for it (ours says "PROFILE").
HEADINGS = {
    "summary": ("summary", "profile"),
    "experience": ("experience",),
    "skills": ("skills",),
    "education": ("education",),
}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_pdf_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def check_ats(text: str, terms: List[str]) -> dict:
    haystack = _collapse(text)
    seen = set()
    term_results = []
    for term in terms:
        key = _collapse(term)
        if not key or key in seen:
            continue
        seen.add(key)
        term_results.append({"term": term, "present": key in haystack})
    short_lines = [_collapse(line) for line in text.splitlines() if len(line.strip()) <= 40]
    return {
        "contact": {"email": bool(EMAIL_RE.search(text)), "phone": bool(PHONE_RE.search(text))},
        "headings": {
            h: any(label in line for line in short_lines for label in labels)
            for h, labels in HEADINGS.items()
        },
        "terms": term_results,
        "text": text,
    }
