"""
In-memory task store. Holds task state during execution.
For a production product, swap this for Redis or a database.
"""
from __future__ import annotations

from .models import Task

_store: dict[str, Task] = {}


def save(task: Task) -> None:
    _store[task.id] = task


def get(task_id: str) -> Task | None:
    return _store.get(task_id)


def delete(task_id: str) -> None:
    _store.pop(task_id, None)
