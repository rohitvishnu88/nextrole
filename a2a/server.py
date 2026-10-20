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

import hmac
import json
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
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
from . import auth
from core import ai_clients, usage
from .routes import profiles, applications, tailor_api, search_brief, job_search as job_search_routes, resume_versions, job_analysis as job_analysis_routes

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

_session_secret = _os.environ.get("SESSION_SECRET")
if not _session_secret:
    if _os.environ.get("TESTING") != "1":
        raise RuntimeError("SESSION_SECRET must be set (a long random string) to sign session cookies")
    _session_secret = "testing-only-secret"
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    same_site="lax",
    https_only=_os.environ.get("PUBLIC_BASE_URL", "").startswith("https://"),
    max_age=30 * 24 * 3600,
)

@app.on_event("startup")
def _claim_unowned_profiles() -> None:
    from . import db, ownership
    owner = db.get_user_by_email(auth.owner_email()) if auth.owner_email() else None
    if owner:
        ownership.assign_unowned_to(owner["id"])


app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(applications.router)
app.include_router(tailor_api.router)
app.include_router(search_brief.router)
app.include_router(job_search_routes.router)
app.include_router(resume_versions.router)
app.include_router(job_analysis_routes.router)


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

def _settle(reservation_id: Optional[str], task: Task) -> None:
    if not reservation_id:
        return
    if task.status.state == TaskState.FAILED:
        usage.release(reservation_id)
    else:
        usage.commit(reservation_id)


async def _run_task(params: TaskSendParams, reservation_id: Optional[str] = None) -> Task:
    with ai_clients.metered(reservation_id):
        task = await _execute_task(params)
    _settle(reservation_id, task)
    return task


async def _execute_task(params: TaskSendParams) -> Task:
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
    rpc_id: Any, params: TaskSendParams, reservation_id: Optional[str] = None
) -> AsyncGenerator[dict, None]:
    holder: dict = {}
    with ai_clients.metered(reservation_id):
        async for event in _stream_task_events(rpc_id, params, holder):
            yield event
    if "task" in holder:
        _settle(reservation_id, holder["task"])


async def _stream_task_events(
    rpc_id: Any, params: TaskSendParams, holder: dict
) -> AsyncGenerator[dict, None]:
    """Execute a task and yield SSE events as it progresses."""
    task = Task(
        id=params.id,
        sessionId=params.sessionId,
        status=TaskStatus(state=TaskState.SUBMITTED),
        messages=[params.message],
    )
    holder["task"] = task
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

# A2A clients can't do Google sign-in, so they use a shared token and act as the owner.
A2A_ACTIONS = {"tailor_resume": "tailor", "search_jobs": "job_search", "analyse_linkedin": "cli"}


def _a2a_authorised(request: Request) -> bool:
    expected = _os.environ.get("A2A_TOKEN", "")
    supplied = request.headers.get("authorization", "")
    if not expected or not supplied.startswith("Bearer "):
        return False
    return hmac.compare_digest(supplied[len("Bearer "):].encode(), expected.encode())


def _reserve_for_owner(rpc_id, params: TaskSendParams):
    """Returns (reservation_id, None), or (None, error response) when a limit is hit."""
    from . import db
    owner = db.get_user_by_email(auth.owner_email()) if auth.owner_email() else None
    action = A2A_ACTIONS.get(_get_skill_id(params), "cli")
    try:
        return usage.reserve(owner["id"] if owner else None, action, is_owner=True), None
    except usage.LimitReached as e:
        error = make_error(rpc_id, -32029, f"Usage limit: {e.code}").model_dump()
        error["error"]["data"] = {"code": e.code, "action": e.action, "resets_on": e.resets_on}
        return None, JSONResponse(error)


@app.post("/")
async def handle_rpc(request: Request):
    if not _a2a_authorised(request):
        return JSONResponse({"detail": "A2A requires Authorization: Bearer <A2A_TOKEN>"}, status_code=401)
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
        reservation_id, refused = _reserve_for_owner(rpc.id, params)
        if refused:
            return refused
        task = await _run_task(params, reservation_id)
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
        reservation_id, refused = _reserve_for_owner(rpc.id, params)
        if refused:
            return refused
        return EventSourceResponse(_stream_task(rpc.id, params, reservation_id))

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
