import uuid
from datetime import datetime, timezone
import sqlite3
from typing import Optional

from app.models.provider import ProviderCreate, ProviderUpdate


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_providers(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT id, name, provider_type, base_url, title_model, vision_model, image_model,
               enabled, is_default, secret_ref, created_at, updated_at
        FROM providers
        ORDER BY is_default DESC, updated_at DESC
        """
    ).fetchall()
    return [_row_to_provider(row) for row in rows]


def get_provider(connection: sqlite3.Connection, provider_id: str) -> Optional[dict]:
    row = connection.execute(
        """
        SELECT id, name, provider_type, base_url, title_model, vision_model, image_model,
               enabled, is_default, secret_ref, created_at, updated_at
        FROM providers
        WHERE id = ?
        """,
        (provider_id,),
    ).fetchone()
    return _row_to_provider(row) if row else None


def create_provider(connection: sqlite3.Connection, payload: ProviderCreate) -> dict:
    provider_id = uuid.uuid4().hex[:12]
    now = _timestamp()

    if payload.is_default:
        connection.execute("UPDATE providers SET is_default = 0")

    connection.execute(
        """
        INSERT INTO providers (
            id, name, provider_type, base_url, title_model, vision_model, image_model,
            enabled, is_default, secret_ref, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider_id,
            payload.name.strip(),
            payload.provider_type.strip(),
            payload.base_url.strip(),
            payload.title_model.strip(),
            payload.vision_model.strip(),
            payload.image_model.strip(),
            int(payload.enabled),
            int(payload.is_default),
            payload.secret_ref.strip(),
            now,
            now,
        ),
    )
    connection.commit()
    return get_provider(connection, provider_id)


def update_provider(
    connection: sqlite3.Connection, provider_id: str, payload: ProviderUpdate
) -> Optional[dict]:
    if payload.is_default:
        connection.execute("UPDATE providers SET is_default = 0")

    connection.execute(
        """
        UPDATE providers
        SET name = ?,
            provider_type = ?,
            base_url = ?,
            title_model = ?,
            vision_model = ?,
            image_model = ?,
            enabled = ?,
            is_default = ?,
            secret_ref = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            payload.name.strip(),
            payload.provider_type.strip(),
            payload.base_url.strip(),
            payload.title_model.strip(),
            payload.vision_model.strip(),
            payload.image_model.strip(),
            int(payload.enabled),
            int(payload.is_default),
            payload.secret_ref.strip(),
            _timestamp(),
            provider_id,
        ),
    )
    connection.commit()
    return get_provider(connection, provider_id)


def delete_provider(connection: sqlite3.Connection, provider_id: str) -> bool:
    cursor = connection.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
    connection.commit()
    return cursor.rowcount > 0


def _row_to_provider(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "provider_type": row["provider_type"],
        "base_url": row["base_url"],
        "title_model": row["title_model"],
        "vision_model": row["vision_model"],
        "image_model": row["image_model"],
        "enabled": bool(row["enabled"]),
        "is_default": bool(row["is_default"]),
        "secret_ref": row["secret_ref"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
