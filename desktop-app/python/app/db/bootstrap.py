import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS providers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        provider_type TEXT NOT NULL,
        base_url TEXT NOT NULL DEFAULT '',
        title_model TEXT NOT NULL DEFAULT '',
        vision_model TEXT NOT NULL DEFAULT '',
        image_model TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        is_default INTEGER NOT NULL DEFAULT 0,
        secret_ref TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS template_groups (
        id TEXT PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        scope TEXT NOT NULL DEFAULT '',
        order_index INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS templates (
        id TEXT PRIMARY KEY,
        group_id TEXT NOT NULL,
        template_key TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        content_json TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        order_index INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(group_id) REFERENCES template_groups(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        project_type TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        record_state TEXT NOT NULL DEFAULT 'active',
        provider_id TEXT NOT NULL DEFAULT '',
        title_language TEXT NOT NULL DEFAULT '',
        image_language TEXT NOT NULL DEFAULT '',
        artifact_dir TEXT NOT NULL DEFAULT '',
        zip_path TEXT NOT NULL DEFAULT '',
        cover_file_id TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        started_at TEXT NOT NULL DEFAULT '',
        completed_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        trashed_at TEXT NOT NULL DEFAULT '',
        purged_at TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_files (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        file_role TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        mime_type TEXT NOT NULL DEFAULT '',
        file_size INTEGER NOT NULL DEFAULT 0,
        width INTEGER NOT NULL DEFAULT 0,
        height INTEGER NOT NULL DEFAULT 0,
        sort_index INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        task_type TEXT NOT NULL,
        status TEXT NOT NULL,
        project_id TEXT NOT NULL DEFAULT '',
        provider_id TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL,
        progress_total INTEGER NOT NULL DEFAULT 0,
        progress_done INTEGER NOT NULL DEFAULT 0,
        current_step TEXT NOT NULL DEFAULT '',
        error_message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        started_at TEXT NOT NULL DEFAULT '',
        ended_at TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_events (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        level TEXT NOT NULL,
        event_type TEXT NOT NULL,
        message TEXT NOT NULL,
        detail_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES tasks(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS diagnostic_snapshots (
        id TEXT PRIMARY KEY,
        snapshot_type TEXT NOT NULL,
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
]

DEFAULT_SETTINGS = {
    "default_title_language": "en",
    "default_image_language": "en",
    "default_model": "nano-banana",
    "default_title_model": "gemini-3.1-flash-lite-preview",
    "default_vision_model": "gemini-3.1-flash-lite-preview",
    "default_output_dir": "",
}


def initialize_database(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)

        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                """
                INSERT INTO settings (key, value_json, updated_at)
                VALUES (?, json(?), datetime('now'))
                ON CONFLICT(key) DO NOTHING
                """,
                (key, f'"{value}"'),
            )

        connection.commit()
    finally:
        connection.close()
