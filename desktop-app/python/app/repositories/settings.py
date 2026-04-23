import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_settings(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        "SELECT key, value_json, updated_at FROM settings ORDER BY key ASC"
    ).fetchall()
    return [_row_to_setting(row) for row in rows]


def get_setting(connection: sqlite3.Connection, key: str) -> Optional[dict]:
    row = connection.execute(
        "SELECT key, value_json, updated_at FROM settings WHERE key = ?",
        (key,),
    ).fetchone()
    return _row_to_setting(row) if row else None


def upsert_setting(connection: sqlite3.Connection, key: str, value: object) -> dict:
    serialized = json.dumps(value, ensure_ascii=False)
    connection.execute(
        """
        INSERT INTO settings (key, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at
        """,
        (key, serialized, _timestamp()),
    )
    connection.commit()
    return get_setting(connection, key)


def _row_to_setting(row: sqlite3.Row) -> dict:
    return {
        "key": row["key"],
        "value": json.loads(row["value_json"]),
        "updated_at": row["updated_at"],
    }
