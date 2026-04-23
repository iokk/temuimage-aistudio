import sqlite3

from fastapi import APIRouter, Depends

from app.api.dependencies import get_db_connection
from app.models.diagnostics import DiagnosticsSummaryResponse

router = APIRouter()


@router.get("/summary", response_model=DiagnosticsSummaryResponse)
def get_diagnostics_summary(
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    providers_total = connection.execute("SELECT COUNT(*) AS count FROM providers").fetchone()["count"]
    providers_enabled = connection.execute(
        "SELECT COUNT(*) AS count FROM providers WHERE enabled = 1"
    ).fetchone()["count"]
    tasks_total = connection.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
    tasks_running = connection.execute(
        "SELECT COUNT(*) AS count FROM tasks WHERE status = 'running'"
    ).fetchone()["count"]
    tasks_failed = connection.execute(
        "SELECT COUNT(*) AS count FROM tasks WHERE status = 'failed'"
    ).fetchone()["count"]
    projects_total = connection.execute("SELECT COUNT(*) AS count FROM projects").fetchone()["count"]
    projects_failed = connection.execute(
        "SELECT COUNT(*) AS count FROM projects WHERE status = 'failed'"
    ).fetchone()["count"]
    projects_succeeded = connection.execute(
        "SELECT COUNT(*) AS count FROM projects WHERE status = 'succeeded'"
    ).fetchone()["count"]
    file_summary = connection.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(file_size), 0) AS size FROM project_files"
    ).fetchone()

    return {
        "providers_total": providers_total,
        "providers_enabled": providers_enabled,
        "tasks_total": tasks_total,
        "tasks_running": tasks_running,
        "tasks_failed": tasks_failed,
        "projects_total": projects_total,
        "projects_failed": projects_failed,
        "projects_succeeded": projects_succeeded,
        "files_total": file_summary["count"],
        "files_size_bytes": file_summary["size"],
    }
