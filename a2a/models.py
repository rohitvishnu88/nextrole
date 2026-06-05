"""
A2A Protocol data models (Google Agent-to-Agent spec).
JSON-RPC 2.0 envelope over HTTP with SSE for streaming.
Python 3.9 compatible.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Task states
# ---------------------------------------------------------------------------

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Message parts
# ---------------------------------------------------------------------------

class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str
    metadata: Optional[Dict[str, Any]] = None


class FileContent(BaseModel):
    name: Optional[str] = None
    mimeType: Optional[str] = None
    bytes: Optional[str] = None   # base64-encoded
    uri: Optional[str] = None


class FilePart(BaseModel):
    type: Literal["file"] = "file"
    file: FileContent
    metadata: Optional[Dict[str, Any]] = None


class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


Part = Annotated[Union[TextPart, FilePart, DataPart], Field(discriminator="type")]


class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: List[Part]
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Artifacts (outputs produced by the agent)
# ---------------------------------------------------------------------------

class Artifact(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    mimeType: Optional[str] = None
    parts: List[Part]
    index: int = 0
    append: Optional[bool] = None
    lastChunk: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class TaskStatus(BaseModel):
    state: TaskState
    message: Optional[Message] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sessionId: Optional[str] = None
    status: TaskStatus
    artifacts: Optional[List[Artifact]] = None
    messages: Optional[List[Message]] = None
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Streaming events
# ---------------------------------------------------------------------------

class TaskStatusUpdateEvent(BaseModel):
    id: str
    status: TaskStatus
    final: bool = False
    metadata: Optional[Dict[str, Any]] = None


class TaskArtifactUpdateEvent(BaseModel):
    id: str
    artifact: Artifact
    final: bool = False
    metadata: Optional[Dict[str, Any]] = None


TaskEvent = Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 envelope
# ---------------------------------------------------------------------------

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[int, str]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[Union[int, str]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[JSONRPCError] = None


# ---------------------------------------------------------------------------
# Task send params
# ---------------------------------------------------------------------------

class TaskSendParams(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sessionId: Optional[str] = None
    message: Message
    historyLength: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskIdParams(BaseModel):
    id: str


# ---------------------------------------------------------------------------
# Standard error codes
# ---------------------------------------------------------------------------

class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TASK_NOT_FOUND = -32001
    TASK_NOT_CANCELABLE = -32002
    UNSUPPORTED_OPERATION = -32004


def make_error(rpc_id: Any, code: int, message: str) -> JSONRPCResponse:
    return JSONRPCResponse(
        id=rpc_id,
        error=JSONRPCError(code=code, message=message),
    )


def agent_message(text: str) -> Message:
    return Message(role="agent", parts=[TextPart(text=text)])
