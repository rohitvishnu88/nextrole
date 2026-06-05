"""
tailor_resume skill — wraps agents/tailor_agent.py.

Accepts a message containing either:
  - A job URL (detected by http/https prefix)
  - Raw JD text (anything else)

Yields status updates during processing, then emits the PDF and
cover letter as base64-encoded file artifacts.
"""
from __future__ import annotations

import asyncio
import base64
import sys
from asyncio import get_event_loop
from pathlib import Path
from typing import AsyncGenerator, Union

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))
import tailor_agent

from ..models import (
    Artifact,
    FilePart,
    FileContent,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
    agent_message,
)

TaskEvent = Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]


def _extract_input(message_text: str) -> tuple[str, str]:
    """Return (job_url, jd_text) from the message. One will be empty."""
    text = message_text.strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text, ""
    # Strip common prefixes like "Tailor my resume to this job description:"
    for prefix in [
        "tailor my resume to this job description:",
        "tailor my resume to this job:",
        "tailor my resume for:",
        "tailor my resume to:",
    ]:
        lower = text.lower()
        if lower.startswith(prefix):
            remainder = text[len(prefix):].strip()
            if remainder.startswith("http"):
                return remainder, ""
            return "", remainder
    return "", text


def _encode_file(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


async def handle(task_id: str, message_text: str) -> AsyncGenerator[TaskEvent, None]:
    job_url, jd_text = _extract_input(message_text)

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=agent_message("Reading job description..."),
        ),
    )

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=agent_message("Tailoring resume to the job description..."),
        ),
    )

    loop = get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: tailor_agent.run(job_url=job_url, jd_text=jd_text),
    )

    if result.get("status") != "completed":
        yield TaskStatusUpdateEvent(
            id=task_id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=agent_message(f"Failed: {result.get('reason', 'Unknown error')}"),
            ),
            final=True,
        )
        return

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.WORKING,
            message=agent_message("Resume and cover letter ready. Packaging artifacts..."),
        ),
    )

    # Emit PDF artifact
    pdf_path = Path(result["pdf_file"])
    if pdf_path.exists():
        yield TaskArtifactUpdateEvent(
            id=task_id,
            artifact=Artifact(
                name=pdf_path.name,
                description="Tailored resume PDF",
                mimeType="application/pdf",
                parts=[FilePart(file=FileContent(
                    name=pdf_path.name,
                    mimeType="application/pdf",
                    bytes=_encode_file(pdf_path),
                ))],
                index=0,
                lastChunk=True,
            ),
        )

    # Emit cover letter artifact
    cl_path = Path(result["cover_letter_file"])
    if cl_path.exists():
        yield TaskArtifactUpdateEvent(
            id=task_id,
            artifact=Artifact(
                name=cl_path.name,
                description="Cover letter",
                mimeType="text/plain",
                parts=[TextPart(text=cl_path.read_text(encoding="utf-8"))],
                index=1,
                lastChunk=True,
            ),
        )

    # Emit JSON artifact (tailored resume data)
    json_path = Path(result["json_file"])
    if json_path.exists():
        yield TaskArtifactUpdateEvent(
            id=task_id,
            artifact=Artifact(
                name=json_path.name,
                description="Tailored resume JSON",
                mimeType="application/json",
                parts=[TextPart(text=json_path.read_text(encoding="utf-8"))],
                index=2,
                lastChunk=True,
            ),
        )

    yield TaskStatusUpdateEvent(
        id=task_id,
        status=TaskStatus(
            state=TaskState.COMPLETED,
            message=agent_message(
                f"Done. Resume PDF, cover letter, and JSON are attached as artifacts."
            ),
        ),
        final=True,
    )
