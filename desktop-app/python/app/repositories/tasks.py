import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_task(
    connection: sqlite3.Connection,
    *,
    task_type: str,
    status: str,
    project_id: str,
    provider_id: str,
    payload: dict,
    progress_total: int = 1,
    progress_done: int = 0,
    current_step: str = "",
    error_message: str = "",
) -> dict:
    task_id = uuid.uuid4().hex[:12]
    now = _timestamp()
    connection.execute(
        """
        INSERT INTO tasks (
            id, task_type, status, project_id, provider_id, payload_json, progress_total,
            progress_done, current_step, error_message, created_at, started_at, ended_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            task_type,
            status,
            project_id,
            provider_id,
            json.dumps(payload, ensure_ascii=False),
            progress_total,
            progress_done,
            current_step,
            error_message,
            now,
            "",
            "",
            now,
        ),
    )
    connection.commit()
    return get_task(connection, task_id)


def update_task(
    connection: sqlite3.Connection,
    task_id: str,
    *,
    status: Optional[str] = None,
    progress_done: Optional[int] = None,
    progress_total: Optional[int] = None,
    current_step: Optional[str] = None,
    error_message: Optional[str] = None,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
) -> Optional[dict]:
    task = get_task(connection, task_id)
    if not task:
        return None

    values = {
        "status": status if status is not None else task["status"],
        "progress_done": progress_done if progress_done is not None else task["progress_done"],
        "progress_total": progress_total if progress_total is not None else task["progress_total"],
        "current_step": current_step if current_step is not None else task["current_step"],
        "error_message": error_message if error_message is not None else task["error_message"],
        "started_at": started_at if started_at is not None else task["started_at"],
        "ended_at": ended_at if ended_at is not None else task["ended_at"],
        "updated_at": _timestamp(),
    }
    connection.execute(
        """
        UPDATE tasks
        SET status = ?,
            progress_done = ?,
            progress_total = ?,
            current_step = ?,
            error_message = ?,
            started_at = ?,
            ended_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            values["status"],
            values["progress_done"],
            values["progress_total"],
            values["current_step"],
            values["error_message"],
            values["started_at"],
            values["ended_at"],
            values["updated_at"],
            task_id,
        ),
    )
    connection.commit()
    return get_task(connection, task_id)


def list_tasks(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT * FROM tasks
        ORDER BY created_at DESC
        """
    ).fetchall()
    return [_row_to_task(row) for row in rows]


def get_task(connection: sqlite3.Connection, task_id: str) -> Optional[dict]:
    row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def add_task_event(
    connection: sqlite3.Connection,
    *,
    task_id: str,
    level: str,
    event_type: str,
    message: str,
    detail: Optional[dict] = None,
) -> dict:
    event_id = uuid.uuid4().hex[:14]
    now = _timestamp()
    connection.execute(
        """
        INSERT INTO task_events (id, task_id, level, event_type, message, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            task_id,
            level,
            event_type,
            message,
            json.dumps(detail or {}, ensure_ascii=False),
            now,
        ),
    )
    connection.commit()
    return get_task_event(connection, event_id)


def list_task_events(connection: sqlite3.Connection, task_id: str) -> list[dict]:
    rows = connection.execute(
        """
        SELECT * FROM task_events
        WHERE task_id = ?
        ORDER BY created_at ASC
        """,
        (task_id,),
    ).fetchall()
    return [_row_to_task_event(row) for row in rows]


def get_task_event(connection: sqlite3.Connection, event_id: str) -> Optional[dict]:
    row = connection.execute("SELECT * FROM task_events WHERE id = ?", (event_id,)).fetchone()
    return _row_to_task_event(row) if row else None


def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_type": row["task_type"],
        "status": row["status"],
        "project_id": row["project_id"],
        "provider_id": row["provider_id"],
        "payload": json.loads(row["payload_json"]),
        "progress_total": row["progress_total"],
        "progress_done": row["progress_done"],
        "current_step": row["current_step"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "updated_at": row["updated_at"],
    }


def _row_to_task_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "level": row["level"],
        "event_type": row["event_type"],
        "message": row["message"],
        "detail": json.loads(row["detail_json"]),
        "created_at": row["created_at"],
    }
