"""
search_jobs skill — wraps agents/job_search_agent.py.

Runs a LinkedIn job search using the candidate's resume_data.json
and returns a ranked list of matching jobs as text + structured data.
"""
from __future__ import annotations

import json
import sys
from asyncio import get_event_loop
from pathlib import Path
from typing import AsyncGenerator, Union

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import job_search_agent

ROOT = Path(__file__).parent.parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"

from ..models import (
    Artifact,
    DataPart,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TextPart,
    agent_message,
)

TaskEvent = Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]


def _load_resume() -> dict:
    with open(RESUME_FILE, encoding="utf-8") as f:
        return json.load(f)


async def handle(task_id: str, message_text: str) -> AsyncGenerator[TaskEvent, None]:
    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=agent_message("Loading resume and starting LinkedIn job search..."),
        ),
    )

    resume = _load_resume()

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=agent_message("Searching LinkedIn for matching jobs. This takes 30-60 seconds..."),
        ),
    )

    loop = get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: job_search_agent.run(resume, include_seen=False),
    )

    jobs = result.get("jobs", [])
    new_count = result.get("new_jobs", len(jobs))

    if not jobs:
        yield TaskStatusUpdateEvent(
            id=task_id,
            status=TaskStatus(
                state=TaskState.COMPLETED,
                message=agent_message("No new matching jobs found this run."),
            ),
            final=True,
        )
        return

    # Build readable summary
    lines = [f"Found {len(jobs)} job(s), {new_count} new:\n"]
    for i, job in enumerate(jobs, 1):
        score = job.get("relevance_score", "?")
        lines.append(f"{i}. [{score}/10] {job['title']} at {job['company']} ({job['location']})")
        lines.append(f"   {job.get('match_reason', '')}")
        lines.append(f"   {job.get('url', '')}\n")

    summary = "\n".join(lines)

    yield TaskArtifactUpdateEvent(
        id=task_id,
        artifact=Artifact(
            name="job_search_results.txt",
            description="Ranked job matches from LinkedIn",
            mimeType="text/plain",
            parts=[TextPart(text=summary)],
            index=0,
            lastChunk=True,
        ),
    )

    # Also emit structured data so calling agents can parse it
    yield TaskArtifactUpdateEvent(
        id=task_id,
        artifact=Artifact(
            name="job_search_results.json",
            description="Structured job match data",
            mimeType="application/json",
            parts=[DataPart(data={"jobs": jobs, "new_jobs": new_count})],
            index=1,
            lastChunk=True,
        ),
    )

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.COMPLETED,
            message=agent_message(f"Search complete. Found {len(jobs)} matching jobs."),
        ),
        final=True,
    )
