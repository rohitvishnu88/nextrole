import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "applications.db"

FOLLOW_UP_DAYS = 7
# Added after the table first shipped; init_db() adds them to existing databases.
_NEW_COLUMNS = {"follow_up_date": "TEXT", "match_score": "INTEGER", "analysis_id": "TEXT"}


def _get_db_path() -> str:
    return os.environ.get("APPLICATIONS_DB", str(_DEFAULT_DB))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(_get_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                job_title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT,
                status TEXT NOT NULL DEFAULT 'saved',
                applied_date TEXT,
                notes TEXT,
                resume_file TEXT,
                cover_letter_file TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(applications)")}
        for column, sql_type in _NEW_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE applications ADD COLUMN {column} {sql_type}")
        conn.commit()


def apply_status_rules(fields: dict, current: Optional[dict], today: date) -> dict:
    """When an application becomes `applied`, fill in the applied date and a follow-up date."""
    if fields.get("status") != "applied":
        return fields
    current = current or {}
    result = dict(fields)
    applied = result.get("applied_date") or current.get("applied_date") or today.isoformat()
    if not current.get("applied_date") or "applied_date" in fields:
        result["applied_date"] = applied
    if "follow_up_date" not in fields and not current.get("follow_up_date"):
        result["follow_up_date"] = (date.fromisoformat(applied) + timedelta(days=FOLLOW_UP_DAYS)).isoformat()
    return result


def is_overdue(row: dict, today: date) -> bool:
    follow_up = row.get("follow_up_date")
    return row.get("status") in ("applied", "interview") and bool(follow_up) and follow_up <= today.isoformat()


def create_application(
    profile_id: str,
    job_title: str,
    company: str,
    location: Optional[str],
    url: Optional[str],
    status: str,
    applied_date: Optional[str],
    notes: Optional[str],
    resume_file: Optional[str],
    cover_letter_file: Optional[str],
    follow_up_date: Optional[str] = None,
    match_score: Optional[int] = None,
    analysis_id: Optional[str] = None,
    today: Optional[date] = None,
) -> str:
    init_db()
    app_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    dates = {"status": status, "applied_date": applied_date}
    if follow_up_date:
        dates["follow_up_date"] = follow_up_date
    dates = apply_status_rules(dates, None, today or date.today())
    with _connect() as conn:
        conn.execute(
            """INSERT INTO applications
               (id, profile_id, job_title, company, location, url, status,
                applied_date, notes, resume_file, cover_letter_file, created_at, updated_at,
                follow_up_date, match_score, analysis_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (app_id, profile_id, job_title, company, location, url, status,
             dates.get("applied_date"), notes, resume_file, cover_letter_file, now, now,
             dates.get("follow_up_date"), match_score, analysis_id),
        )
        conn.commit()
    return app_id


def list_applications(profile_id: str, today: Optional[date] = None) -> list:
    init_db()
    today = today or date.today()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE profile_id = ? ORDER BY updated_at DESC",
            (profile_id,),
        ).fetchall()
    return [dict(r, overdue=is_overdue(dict(r), today)) for r in rows]


def get_application(app_id: str) -> Optional[dict]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return dict(row) if row else None


def update_application(app_id: str, fields: dict, today: Optional[date] = None) -> bool:
    allowed = {
        "job_title", "company", "location", "url", "status",
        "applied_date", "notes", "resume_file", "cover_letter_file",
        "follow_up_date", "match_score", "analysis_id",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    current = get_application(app_id)
    if current is None:
        return False
    updates = apply_status_rules(updates, current, today or date.today())
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [app_id]
    with _connect() as conn:
        conn.execute(f"UPDATE applications SET {set_clause} WHERE id = ?", values)
        conn.commit()
    return True


def delete_application(app_id: str) -> bool:
    with _connect() as conn:
        result = conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        conn.commit()
    return result.rowcount > 0
