from fastapi import APIRouter, HTTPException, Request

from app.models.task import TaskEventResponse, TaskResponse
from app.services.title_workflow import get_task_snapshot, list_task_event_snapshots, list_task_snapshots

router = APIRouter()


@router.get("", response_model=list[TaskResponse])
def get_tasks(request: Request):
    return list_task_snapshots(request.app)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task_detail(task_id: str, request: Request):
    task = get_task_snapshot(request.app, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/{task_id}/events", response_model=list[TaskEventResponse])
def get_task_events(task_id: str, request: Request):
    return list_task_event_snapshots(request.app, task_id)
