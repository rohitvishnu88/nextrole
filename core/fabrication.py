"""Flag claims in a tailored resume that don't appear anywhere in the base resume.

False positives are acceptable: every flag is something for the candidate to confirm,
not an error. Missing sections are treated as empty.
"""
import re
from typing import Iterator, List, Tuple

NUMBER_RE = re.compile(r"[£$€]?\d[\d,.]*\s?(?:%|bn|k|m|x|\+)?", re.I)
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")
IDENTITY_FIELDS = ("title", "company", "start_date", "end_date")
TOP_IDENTITY_FIELDS = ("name", "designation", "email", "phone")


def _strings(value) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _skills(resume: dict) -> List[str]:
    return [s for s in _strings(resume.get("skills") or []) if s.strip()]


def _prose(resume: dict) -> Iterator[Tuple[str, str]]:
    if resume.get("summary"):
        yield "summary", resume["summary"]
    for i, exp in enumerate(resume.get("experience") or []):
        if exp.get("highlight"):
            yield f"experience[{i}].highlight", exp["highlight"]
        for j, bullet in enumerate(exp.get("description") or []):
            yield f"experience[{i}].description[{j}]", bullet


def _looks_like_name(token: str) -> bool:
    letters = [c for c in token if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return True
    return any(c.isdigit() for c in token) or any(c.isupper() for c in token[1:])


def find_fabrications(base: dict, tailored: dict) -> List[dict]:
    corpus = "\n".join(_strings(base)).lower()
    compact = re.sub(r"\s+", "", corpus)
    flags: List[dict] = []

    def add(location: str, kind: str, text: str) -> None:
        flag = {"location": location, "kind": kind, "text": text}
        if flag not in flags:
            flags.append(flag)

    for location, text in _prose(tailored):
        for match in NUMBER_RE.finditer(text):
            number = re.sub(r"\s+", "", match.group()).rstrip(".,")
            if number and number.lower() not in compact:
                add(location, "number", number)
        for match in TOKEN_RE.finditer(text):
            token = match.group().rstrip("./-")
            if _looks_like_name(token) and token.lower() not in corpus:
                add(location, "name", token)

    for skill in _skills(tailored):
        if skill.lower() not in corpus:
            add("skills", "skill", skill)

    base_exp = base.get("experience") or []
    for i, exp in enumerate(tailored.get("experience") or []):
        original = base_exp[i] if i < len(base_exp) else {}
        for field in IDENTITY_FIELDS:
            if exp.get(field, "") != original.get(field, ""):
                add(f"experience[{i}]", "identity", f"{field}: {exp.get(field, '')}")
    for field in TOP_IDENTITY_FIELDS:
        if field in tailored and tailored.get(field) != base.get(field):
            add(field, "identity", f"{field}: {tailored.get(field)}")

    return flags
