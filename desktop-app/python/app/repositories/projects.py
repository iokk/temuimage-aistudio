import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any, Optional


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_project(
    connection: sqlite3.Connection,
    *,
    project_type: str,
    summary: str,
    status: str,
    provider_id: str,
    title_language: str,
    image_language: str,
    artifact_dir: str,
) -> dict:
    project_id = uuid.uuid4().hex[:12]
    now = _timestamp()
    connection.execute(
        """
        INSERT INTO projects (
            id, project_type, summary, status, record_state, provider_id,
            title_language, image_language, artifact_dir, zip_path, cover_file_id,
            created_at, started_at, completed_at, updated_at, trashed_at, purged_at
        ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, '', '', ?, '', '', ?, '', '')
        """,
        (
            project_id,
            project_type,
            summary,
            status,
            provider_id,
            title_language,
            image_language,
            artifact_dir,
            now,
            now,
        ),
    )
    connection.commit()
    return get_project(connection, project_id)


def update_project_status(
    connection: sqlite3.Connection,
    project_id: str,
    *,
    status: str,
    completed: bool = False,
) -> Optional[dict]:
    project = get_project(connection, project_id)
    if not project:
        return None

    now = _timestamp()
    completed_at = now if completed else project["completed_at"]
    started_at = project["started_at"] or now
    connection.execute(
        """
        UPDATE projects
        SET status = ?,
            started_at = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (status, started_at, completed_at, now, project_id),
    )
    connection.commit()
    return get_project(connection, project_id)


def add_project_file(
    connection: sqlite3.Connection,
    *,
    project_id: str,
    file_role: str,
    file_path: str,
    mime_type: str,
    sort_index: int = 0,
) -> dict:
    file_id = uuid.uuid4().hex[:14]
    path = Path(file_path)
    file_size = path.stat().st_size if path.exists() else 0
    now = _timestamp()
    connection.execute(
        """
        INSERT INTO project_files (
            id, project_id, file_role, file_name, file_path, mime_type,
            file_size, width, height, sort_index, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (
            file_id,
            project_id,
            file_role,
            path.name,
            str(path),
            mime_type,
            file_size,
            sort_index,
            now,
        ),
    )
    connection.commit()
    return get_project_file(connection, file_id)


def list_projects(connection: sqlite3.Connection, record_state: str = "active") -> list[dict]:
    if record_state == "all":
        rows = connection.execute(
            """
            SELECT * FROM projects
            ORDER BY created_at DESC
            """
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT * FROM projects
            WHERE record_state = ?
            ORDER BY created_at DESC
            """,
            (record_state,),
        ).fetchall()
    return [_row_to_project(row) for row in rows]


def trash_project(connection: sqlite3.Connection, project_id: str) -> Optional[dict]:
    project = get_project(connection, project_id)
    if not project:
        return None
    now = _timestamp()
    connection.execute(
        """
        UPDATE projects
        SET record_state = 'trashed',
            trashed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, now, project_id),
    )
    connection.commit()
    return get_project(connection, project_id)


def restore_project(connection: sqlite3.Connection, project_id: str) -> Optional[dict]:
    project = get_project(connection, project_id)
    if not project:
        return None
    now = _timestamp()
    connection.execute(
        """
        UPDATE projects
        SET record_state = 'active',
            trashed_at = '',
            updated_at = ?
        WHERE id = ?
        """,
        (now, project_id),
    )
    connection.commit()
    return get_project(connection, project_id)


def purge_project(connection: sqlite3.Connection, project_id: str) -> bool:
    project = get_project(connection, project_id)
    if not project:
        return False
    artifact_dir = project["artifact_dir"]
    connection.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
    connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    connection.commit()
    if artifact_dir:
        shutil.rmtree(artifact_dir, ignore_errors=True)
    return True


def get_project(connection: sqlite3.Connection, project_id: str) -> Optional[dict]:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        return None
    project = _row_to_project(row)
    project["files"] = list_project_files(connection, project_id)
    project["title_text"] = load_project_title_text(project["files"])
    return project


def list_project_files(connection: sqlite3.Connection, project_id: str) -> list[dict]:
    rows = connection.execute(
        """
        SELECT * FROM project_files
        WHERE project_id = ?
        ORDER BY sort_index ASC, created_at ASC
        """,
        (project_id,),
    ).fetchall()
    return [_row_to_project_file(row) for row in rows]


def get_project_file(connection: sqlite3.Connection, file_id: str) -> Optional[dict]:
    row = connection.execute("SELECT * FROM project_files WHERE id = ?", (file_id,)).fetchone()
    return _row_to_project_file(row) if row else None


def load_project_title_text(files: list[dict]) -> str:
    title_file = next((file for file in files if file["file_role"] == "title_output"), None)
    if not title_file:
        return ""
    try:
        return Path(title_file["file_path"]).read_text(encoding="utf-8")
    except OSError:
        return ""


def _row_to_project(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_type": row["project_type"],
        "summary": row["summary"],
        "status": row["status"],
        "record_state": row["record_state"],
        "provider_id": row["provider_id"],
        "title_language": row["title_language"],
        "image_language": row["image_language"],
        "artifact_dir": row["artifact_dir"],
        "zip_path": row["zip_path"],
        "cover_file_id": row["cover_file_id"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "updated_at": row["updated_at"],
        "trashed_at": row["trashed_at"],
        "purged_at": row["purged_at"],
    }


def _row_to_project_file(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "file_role": row["file_role"],
        "file_name": row["file_name"],
        "file_path": row["file_path"],
        "mime_type": row["mime_type"],
        "file_size": row["file_size"],
        "width": row["width"],
        "height": row["height"],
        "sort_index": row["sort_index"],
        "created_at": row["created_at"],
    }
