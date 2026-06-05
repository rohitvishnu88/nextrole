import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "applications.db"


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
        conn.commit()


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
) -> str:
    init_db()
    app_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO applications
               (id, profile_id, job_title, company, location, url, status,
                applied_date, notes, resume_file, cover_letter_file, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (app_id, profile_id, job_title, company, location, url, status,
             applied_date, notes, resume_file, cover_letter_file, now, now),
        )
        conn.commit()
    return app_id


def list_applications(profile_id: str) -> list:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE profile_id = ? ORDER BY updated_at DESC",
            (profile_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_application(app_id: str, fields: dict) -> bool:
    allowed = {
        "job_title", "company", "location", "url", "status",
        "applied_date", "notes", "resume_file", "cover_letter_file",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
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
