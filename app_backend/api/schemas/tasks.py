from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class TaskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: str
    timestamp: str
    message: str | None = None
    payload: dict[str, Any] | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    task_type: str
    state: str
    created_at: str
    updated_at: str
    events: list[TaskEventResponse]
    result: dict[str, Any] | None = None
    error: str | None = None
    pending_conflict: dict[str, Any] | None = None

