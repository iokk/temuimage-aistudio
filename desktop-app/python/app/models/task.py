from typing import Any

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    id: str
    task_type: str
    status: str
    project_id: str
    provider_id: str
    payload: dict[str, Any]
    progress_total: int
    progress_done: int
    current_step: str
    error_message: str
    created_at: str
    started_at: str
    ended_at: str
    updated_at: str


class TaskEventResponse(BaseModel):
    id: str
    task_id: str
    level: str
    event_type: str
    message: str
    detail: dict[str, Any]
    created_at: str
