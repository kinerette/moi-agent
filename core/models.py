"""Pydantic models partagés."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"


class SafetyLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    instruction: str
    status: TaskStatus = TaskStatus.PENDING
    steps: list[str] = Field(default_factory=list)
    current_step: int = 0
    result: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "dashboard"  # dashboard | telegram | auto


class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str
    ts: datetime = Field(default_factory=datetime.utcnow)
    model_used: str = ""


class ToolCall(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    name: str
    output: str
    success: bool = True
    screenshot: str | None = None  # base64
