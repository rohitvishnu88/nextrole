from fastapi import APIRouter, Depends

from a2a import db
from a2a.auth import User, current_user
from core import limits, usage

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/me")
def usage_me(user: User = Depends(current_user)):
    month = usage.month_of()
    counts = usage.counts_for(user.id, month)
    spent = usage.spent_this_month()
    body = {
        "month": month,
        "resets_on": usage.resets_on(month),
        "paused": spent >= limits.MONTHLY_BUDGET_USD,
        "actions": {
            action: {"used": counts.get(action, 0), "limit": None if user.is_owner else limit}
            for action, limit in limits.ACTION_LIMITS.items()
        },
    }
    if user.is_owner:
        summary = usage.summary(month)
        by_user = []
        for entry in summary["by_user"]:
            row = db.get_user(entry["user_id"]) if entry["user_id"] else None
            by_user.append({
                "email": row["email"] if row else "command line / A2A",
                "spent_usd": round(entry["spent_usd"], 4),
                "counts": entry["counts"],
            })
        body["owner"] = {
            "spent_usd": round(spent, 4),
            "budget_usd": limits.MONTHLY_BUDGET_USD,
            "by_user": sorted(by_user, key=lambda u: -u["spent_usd"]),
            "by_action": {a: round(v, 4) for a, v in summary["by_action"].items()},
        }
    return body
