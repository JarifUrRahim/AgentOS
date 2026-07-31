"""Request bodies for the AgentOS HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentos.core.permissions import PermissionLevel


class ChatRequest(BaseModel):
    instruction: str = Field(min_length=1)
    actor: str | None = None


class ActionRequest(BaseModel):
    """Manual control layer: run one registered action directly."""

    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    actor: str | None = None


class MemoryRequest(BaseModel):
    namespace: str
    key: str
    value: Any


class PermissionRequest(BaseModel):
    level: PermissionLevel
    actor: str | None = None
