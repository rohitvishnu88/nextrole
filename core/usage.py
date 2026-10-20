"""Usage ledger: per-user monthly allowances and a hard monthly spending ceiling.

An action reserves its worst-case cost before it starts, records the measured cost of
each call it makes, then commits (counts against the allowance) or releases (doesn't).
Released runs still count towards the ceiling: that money was spent.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

from core import limits

_DEFAULT_DB = Path(__file__).parent.parent / "data" / "applications.db"

# A reservation still open after this long belongs to a run that died (server restart,
# dropped stream); it's released so it stops holding allowance and budget.
STALE_AFTER = timedelta(minutes=60)


class LimitReached(Exception):
    def __init__(self, code: str, action: str, resets_on: str):
        super().__init__(f"{code}: {action} (resets {resets_on})")
        self.code = code
        self.action = action
        self.resets_on = resets_on


def _connect() -> sqlite3.Connection:
    path = os.environ.get("APPLICATIONS_DB", str(_DEFAULT_DB))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            month TEXT NOT NULL,
            estimate_usd REAL NOT NULL,
            cost_usd REAL NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            tavily_credits INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    return conn


def month_of(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def resets_on(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{year + 1}-01-01" if mon == 12 else f"{year}-{mon + 1:02d}-01"


def _spent(conn: sqlite3.Connection, month: str) -> float:
    row = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN status = 'reserved' THEN MAX(estimate_usd, cost_usd)
                                    ELSE cost_usd END), 0) AS spent
           FROM usage WHERE month = ?""",
        (month,),
    ).fetchone()
    return float(row["spent"])


def reserve(user_id: Optional[str], action: str, is_owner: bool, now: Optional[datetime] = None) -> str:
    month = month_of(now)
    estimate = limits.ACTION_ESTIMATES_USD[action]
    conn = _connect()
    try:
        # One write transaction, so two simultaneous reserves can't both pass the checks.
        conn.execute("BEGIN IMMEDIATE")
        current = now or datetime.now(timezone.utc)
        conn.execute(
            "UPDATE usage SET status = 'released' WHERE status = 'reserved' AND created_at < ?",
            ((current - STALE_AFTER).isoformat(),),
        )
        if not is_owner and action in limits.ACTION_LIMITS:
            used = conn.execute(
                "SELECT COUNT(*) FROM usage WHERE user_id = ? AND action = ? AND month = ? AND status != 'released'",
                (user_id, action, month),
            ).fetchone()[0]
            if used >= limits.ACTION_LIMITS[action]:
                raise LimitReached("limit_reached", action, resets_on(month))
        if _spent(conn, month) + estimate > limits.MONTHLY_BUDGET_USD:
            raise LimitReached("budget_reached", action, resets_on(month))
        reservation_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO usage (id, user_id, action, status, month, estimate_usd, created_at) VALUES (?,?,?,?,?,?,?)",
            (reservation_id, user_id, action, "reserved", month, estimate, current.isoformat()),
        )
        conn.execute("COMMIT")
        return reservation_id
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def record_call(reservation_id: Optional[str], *, model: str = "", input_tokens: int = 0, output_tokens: int = 0,
                cache_read_tokens: int = 0, cache_write_tokens: int = 0, tavily_credits: int = 0) -> None:
    if not reservation_id:
        return
    cost = tavily_credits * limits.TAVILY_CREDIT_USD
    if model:
        price = limits.price_for(model)
        cost += (
            input_tokens * price["input"]
            + output_tokens * price["output"]
            + cache_read_tokens * price["input"] * limits.CACHE_READ_MULTIPLIER
            + cache_write_tokens * price["input"] * limits.CACHE_WRITE_MULTIPLIER
        ) / 1_000_000
    conn = _connect()
    try:
        conn.execute(
            """UPDATE usage SET cost_usd = cost_usd + ?, input_tokens = input_tokens + ?,
                   output_tokens = output_tokens + ?, tavily_credits = tavily_credits + ? WHERE id = ?""",
            (cost, input_tokens + cache_read_tokens + cache_write_tokens, output_tokens, tavily_credits, reservation_id),
        )
    finally:
        conn.close()


def _set_status(reservation_id: str, status: str) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE usage SET status = ? WHERE id = ? AND status = 'reserved'", (status, reservation_id))
    finally:
        conn.close()


def commit(reservation_id: str) -> None:
    _set_status(reservation_id, "committed")


def release(reservation_id: str) -> None:
    _set_status(reservation_id, "released")


def spent_this_month(now: Optional[datetime] = None) -> float:
    conn = _connect()
    try:
        return _spent(conn, month_of(now))
    finally:
        conn.close()


def counts_for(user_id: str, month: str) -> Dict[str, int]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT action, COUNT(*) AS n FROM usage WHERE user_id = ? AND month = ? AND status != 'released' GROUP BY action",
            (user_id, month),
        ).fetchall()
    finally:
        conn.close()
    return {r["action"]: r["n"] for r in rows}


def summary(month: str) -> dict:
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT user_id, action, COUNT(*) AS n,
                      SUM(CASE WHEN status = 'reserved' THEN MAX(estimate_usd, cost_usd) ELSE cost_usd END) AS spent
               FROM usage WHERE month = ? GROUP BY user_id, action""",
            (month,),
        ).fetchall()
    finally:
        conn.close()
    by_user: Dict[Optional[str], dict] = {}
    by_action: Dict[str, float] = {}
    for r in rows:
        entry = by_user.setdefault(r["user_id"], {"user_id": r["user_id"], "spent_usd": 0.0, "counts": {}})
        entry["spent_usd"] += r["spent"]
        entry["counts"][r["action"]] = r["n"]
        by_action[r["action"]] = by_action.get(r["action"], 0.0) + r["spent"]
    return {"by_user": list(by_user.values()), "by_action": by_action}
