"""Reserve an action's allowance before it starts; commit on success, release on failure."""
from typing import Callable, Optional

from fastapi import HTTPException

from a2a.auth import User
from core import ai_clients, usage


def start(user: User, action: str) -> str:
    try:
        return usage.reserve(user.id, action, user.is_owner)
    except usage.LimitReached as e:
        raise HTTPException(status_code=429, detail={"code": e.code, "action": e.action, "resets_on": e.resets_on})


def run(reservation_id: Optional[str], fn: Callable, *args, **kwargs):
    """Call fn with its Claude/Tavily calls metered against the reservation. Call this
    inside the thread that does the work, so the reservation is visible to the calls."""
    if reservation_id is None:
        return fn(*args, **kwargs)
    with ai_clients.metered(reservation_id):
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            usage.release(reservation_id)
            raise
    usage.commit(reservation_id)
    return result
