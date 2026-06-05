"""
A2A-compliant FastAPI server.

Endpoints:
  GET  /.well-known/agent.json   — agent card (discovery)
  POST /                         — JSON-RPC 2.0 task handler

Supported JSON-RPC methods:
  tasks/send           — run a task synchronously, return completed Task
  tasks/sendSubscribe  — stream task progress as SSE events
  tasks/get            — retrieve a stored task by ID
  tasks/cancel         — cancel a running task (not yet supported)
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .agent_card import AGENT_CARD
from . import task_store
from .models import (
    Artifact,
    ErrorCode,
    JSONRPCRequest,
    JSONRPCResponse,
    Task,
    TaskIdParams,
    TaskSendParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskEvent,
    agent_message,
    make_error,
)
from .skills import tailor, job_search, linkedin
from .routes import profiles, applications, tailor_api, search_brief

app = FastAPI(
    title="Resume Builder A2A Agent",
    description="A2A-compatible agent for resume tailoring, job search, and LinkedIn analysis.",
    version="1.0.0",
)

import os as _os
_cors_origins = _os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(applications.router)
app.include_router(tailor_api.router)
app.include_router(search_brief.router)


# ---------------------------------------------------------------------------
# Agent card
# ---------------------------------------------------------------------------

@app.get("/.well-known/agent.json", include_in_schema=False)
async def agent_card():
    return AGENT_CARD


# ---------------------------------------------------------------------------
# Skill router
# ---------------------------------------------------------------------------

def _get_skill_id(params: TaskSendParams) -> str:
    """
    Determine which skill to invoke.
    Priority: explicit metadata.skill > keyword detection in message text.
    """
    if params.metadata and params.metadata.get("skill"):
        return params.metadata["skill"]

    text = " ".join(
        p.text for p in params.message.parts if hasattr(p, "text")
    ).lower()

    if any(k in text for k in ["tailor", "cover letter", "resume", "jd", "job description"]):
        return "tailor_resume"
    if any(k in text for k in ["search", "find jobs", "linkedin jobs"]):
        return "search_jobs"
    if any(k in text for k in ["linkedin", "profile", "analyse"]):
        return "analyse_linkedin"

    return "tailor_resume"


def _get_handler(skill_id: str):
    handlers = {
        "tailor_resume": tailor.handle,
        "search_jobs": job_search.handle,
        "analyse_linkedin": linkedin.handle,
    }
    return handlers.get(skill_id)


def _extract_text(params: TaskSendParams) -> str:
    return "\n".join(
        p.text for p in params.message.parts if hasattr(p, "text")
    ).strip()


# ---------------------------------------------------------------------------
# Task execution helpers
# ---------------------------------------------------------------------------

async def _run_task(params: TaskSendParams) -> Task:
    """Execute a task synchronously, collecting all events."""
    task = Task(
        id=params.id,
        sessionId=params.sessionId,
        status=TaskStatus(state=TaskState.SUBMITTED),
        messages=[params.message],
    )
    task_store.save(task)

    skill_id = _get_skill_id(params)
    handler = _get_handler(skill_id)

    if handler is None:
        task.status = TaskStatus(
            state=TaskState.FAILED,
            message=agent_message(f"Unknown skill: {skill_id}"),
        )
        task_store.save(task)
        return task

    message_text = _extract_text(params)

    try:
        async for event in handler(task.id, message_text):
            if isinstance(event, TaskStatusUpdateEvent):
                task.status = event.status
            elif isinstance(event, TaskArtifactUpdateEvent):
                if task.artifacts is None:
                    task.artifacts = []
                task.artifacts.append(event.artifact)
            task_store.save(task)
    except Exception as exc:
        task.status = TaskStatus(
            state=TaskState.FAILED,
            message=agent_message(f"Internal error: {exc}"),
        )
        task_store.save(task)

    return task


async def _stream_task(
    rpc_id: Any, params: TaskSendParams
) -> AsyncGenerator[dict, None]:
    """Execute a task and yield SSE events as it progresses."""
    task = Task(
        id=params.id,
        sessionId=params.sessionId,
        status=TaskStatus(state=TaskState.SUBMITTED),
        messages=[params.message],
    )
    task_store.save(task)

    skill_id = _get_skill_id(params)
    handler = _get_handler(skill_id)

    if handler is None:
        event = TaskStatusUpdateEvent(
            id=task.id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=agent_message(f"Unknown skill: {skill_id}"),
            ),
            final=True,
        )
        yield {"data": JSONRPCResponse(
            id=rpc_id, result=event.model_dump()
        ).model_dump_json()}
        return

    message_text = _extract_text(params)

    try:
        async for event in handler(task.id, message_text):
            if isinstance(event, TaskStatusUpdateEvent):
                task.status = event.status
            elif isinstance(event, TaskArtifactUpdateEvent):
                if task.artifacts is None:
                    task.artifacts = []
                task.artifacts.append(event.artifact)
            task_store.save(task)

            yield {"data": JSONRPCResponse(
                id=rpc_id, result=event.model_dump()
            ).model_dump_json()}

    except Exception as exc:
        error_event = TaskStatusUpdateEvent(
            id=task.id,
            status=TaskStatus(
                state=TaskState.FAILED,
                message=agent_message(f"Internal error: {exc}"),
            ),
            final=True,
        )
        task.status = error_event.status
        task_store.save(task)
        yield {"data": JSONRPCResponse(
            id=rpc_id, result=error_event.model_dump()
        ).model_dump_json()}


# ---------------------------------------------------------------------------
# JSON-RPC dispatcher
# ---------------------------------------------------------------------------

@app.post("/")
async def handle_rpc(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            make_error(None, ErrorCode.PARSE_ERROR, "Invalid JSON").model_dump(),
            status_code=400,
        )

    try:
        rpc = JSONRPCRequest(**body)
    except Exception:
        return JSONResponse(
            make_error(None, ErrorCode.INVALID_REQUEST, "Invalid JSON-RPC request").model_dump(),
            status_code=400,
        )

    method = rpc.method

    # tasks/send — synchronous
    if method == "tasks/send":
        try:
            params = TaskSendParams(**(rpc.params or {}))
        except Exception as e:
            return JSONResponse(
                make_error(rpc.id, ErrorCode.INVALID_PARAMS, str(e)).model_dump()
            )
        task = await _run_task(params)
        return JSONResponse(
            JSONRPCResponse(id=rpc.id, result=task.model_dump()).model_dump()
        )

    # tasks/sendSubscribe — streaming via SSE
    elif method == "tasks/sendSubscribe":
        try:
            params = TaskSendParams(**(rpc.params or {}))
        except Exception as e:
            return JSONResponse(
                make_error(rpc.id, ErrorCode.INVALID_PARAMS, str(e)).model_dump()
            )
        return EventSourceResponse(_stream_task(rpc.id, params))

    # tasks/get — retrieve stored task
    elif method == "tasks/get":
        try:
            id_params = TaskIdParams(**(rpc.params or {}))
        except Exception as e:
            return JSONResponse(
                make_error(rpc.id, ErrorCode.INVALID_PARAMS, str(e)).model_dump()
            )
        task = task_store.get(id_params.id)
        if task is None:
            return JSONResponse(
                make_error(rpc.id, ErrorCode.TASK_NOT_FOUND, f"Task {id_params.id} not found").model_dump()
            )
        return JSONResponse(
            JSONRPCResponse(id=rpc.id, result=task.model_dump()).model_dump()
        )

    # tasks/cancel — not supported yet
    elif method == "tasks/cancel":
        return JSONResponse(
            make_error(rpc.id, ErrorCode.UNSUPPORTED_OPERATION, "Task cancellation not supported").model_dump()
        )

    else:
        return JSONResponse(
            make_error(rpc.id, ErrorCode.METHOD_NOT_FOUND, f"Method not found: {method}").model_dump()
        )
