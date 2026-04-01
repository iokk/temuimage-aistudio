from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.core.auth import Principal, require_admin, require_team_member
from apps.api.job_repository import job_repository


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectSelectRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=120)


@router.get("")
def list_projects(principal: Principal = Depends(require_team_member)):
    return job_repository.list_projects(user_id=principal.user_id)


@router.post("")
def create_project(
    payload: ProjectCreateRequest,
    principal: Principal = Depends(require_admin),
):
    normalized_name = str(payload.name or "").strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Project name is required")
    try:
        return job_repository.create_project(
            user_id=principal.user_id, name=normalized_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/current")
def current_project(principal: Principal = Depends(require_team_member)):
    account_state = job_repository.get_account_team_state(user_id=principal.user_id)
    return {"project": account_state.get("current_project")}


@router.put("/current")
def update_current_project(
    payload: ProjectUpdateRequest,
    principal: Principal = Depends(require_admin),
):
    normalized_name = str(payload.name or "").strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Project name is required")

    try:
        account_state = job_repository.update_current_project(
            user_id=principal.user_id,
            name=normalized_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project": account_state.get("current_project")}


@router.put("/current/select")
def select_current_project(
    payload: ProjectSelectRequest,
    principal: Principal = Depends(require_team_member),
):
    normalized_project_id = str(payload.project_id or "").strip()
    if not normalized_project_id:
        raise HTTPException(status_code=400, detail="Project id is required")
    try:
        return job_repository.select_current_project(
            user_id=principal.user_id,
            project_id=normalized_project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
