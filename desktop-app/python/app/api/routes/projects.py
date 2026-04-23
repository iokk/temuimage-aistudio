import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.dependencies import get_db_connection
from app.models.project import ProjectResponse
from app.repositories.projects import (
    get_project,
    list_projects,
    purge_project,
    restore_project,
    trash_project,
)

router = APIRouter()


@router.get("", response_model=list[ProjectResponse])
def get_projects(
    record_state: str = Query(default="all"),
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return list_projects(connection, record_state=record_state)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_detail(
    project_id: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    project = get_project(connection, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/trash", response_model=ProjectResponse)
def post_project_trash(
    project_id: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    project = trash_project(connection, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/{project_id}/restore", response_model=ProjectResponse)
def post_project_restore(
    project_id: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    project = restore_project(connection, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    deleted = purge_project(connection, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}
