"""
analyse_linkedin skill — wraps agents/linkedin_agent.py.

Reads the LinkedIn data export from data/linkedin_export/ and
compares it to resume_data.json, returning profile update recommendations.
"""
from __future__ import annotations

import json
import sys
from asyncio import get_event_loop
from pathlib import Path
from typing import AsyncGenerator, Union

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import linkedin_agent

ROOT = Path(__file__).parent.parent.parent
RESUME_FILE = ROOT / "data" / "resume_data.json"

from ..models import (
    Artifact,
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
            message=agent_message("Reading LinkedIn export and resume data..."),
        ),
    )

    resume = _load_resume()

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=agent_message("Comparing LinkedIn profile to resume. Identifying gaps..."),
        ),
    )

    loop = get_event_loop()
    result = await loop.run_in_executor(None, lambda: linkedin_agent.run(resume))

    if result.get("status") == "skipped":
        yield TaskStatusUpdateEvent(
            id=task_id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=agent_message(f"Skipped: {result.get('reason')}"),
            ),
            final=True,
        )
        return

    updates = result.get("updates", {})
    gaps = updates.get("gaps_identified", [])
    missing_skills = updates.get("missing_skills", [])
    headline = updates.get("headline", {})
    summary = updates.get("summary", {})
    positions = updates.get("position_updates", [])
    missing_certs = updates.get("missing_certifications", [])

    lines = ["# LinkedIn Profile Analysis\n"]

    if gaps:
        lines.append(f"## Gaps identified ({len(gaps)})")
        for g in gaps:
            lines.append(f"- {g}")
        lines.append("")

    if headline.get("suggested"):
        lines.append("## Headline update")
        lines.append(f"Current:   {headline.get('current', '(empty)')}")
        lines.append(f"Suggested: {headline['suggested']}")
        lines.append(f"Why: {headline.get('reason', '')}\n")

    if summary.get("suggested"):
        lines.append("## About / Summary update")
        lines.append(f"Suggested:\n{summary['suggested']}\n")

    if missing_skills:
        lines.append(f"## Missing skills ({len(missing_skills)})")
        lines.append(", ".join(missing_skills))
        lines.append("")

    if missing_certs:
        lines.append(f"## Missing certifications ({len(missing_certs)})")
        for c in missing_certs:
            lines.append(f"- {c}")
        lines.append("")

    if positions:
        lines.append(f"## Role descriptions to update ({len(positions)})")
        for p in positions:
            lines.append(f"\n### {p.get('title')} at {p.get('company')}")
            lines.append(f"Suggested:\n{p.get('suggested_description', '')}")

    report = "\n".join(lines)

    yield TaskArtifactUpdateEvent(
        id=task_id,
        artifact=Artifact(
            name="linkedin_analysis.md",
            description="LinkedIn profile gap analysis and update recommendations",
            mimeType="text/markdown",
            parts=[TextPart(text=report)],
            index=0,
            lastChunk=True,
        ),
    )

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.COMPLETED,
            message=agent_message(
                f"Analysis complete. {len(gaps)} gaps identified. Report attached."
            ),
        ),
        final=True,
    )
