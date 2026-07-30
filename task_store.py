"""Persistent task storage and lifecycle transitions for TuLite."""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional, Union

from task_status import TASK_STATUS_TRANSITIONS


SCHEMA_VERSION = 2
DEFAULT_RUNNER_LEASE_SECONDS = 30
INVALID_AVAILABLE_AT_SENTINEL = "9999-12-31T23:59:59.999999+00:00"


def _normalize_available_at(value) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except (TypeError, ValueError) as error:
            raise ValueError("available_at must be a valid ISO timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


class TaskCapacityError(RuntimeError):
    pass


class SqliteTaskStore:
    """Transactional task repository using one short SQLite connection per call."""

    def __init__(
        self,
        path: Path,
        lock: Optional[threading.RLock] = None,
        legacy_json_path: Optional[Path] = None,
    ):
        self.path = Path(path)
        self.legacy_json_path = Path(legacy_json_path) if legacy_json_path else None
        self._lock = lock or threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._migrate_legacy_json()

    def list(
        self,
        scope_owner_id: Optional[str] = None,
        include_unowned: bool = False,
    ) -> list:
        with self._lock, self._connect() as connection:
            if scope_owner_id is None:
                rows = connection.execute(
                    "SELECT document FROM tasks ORDER BY created_at DESC"
                ).fetchall()
            elif include_unowned:
                rows = connection.execute(
                    "SELECT document FROM tasks WHERE owner_id = ? OR owner_id = '' "
                    "ORDER BY created_at DESC",
                    (str(scope_owner_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT document FROM tasks WHERE owner_id = ? "
                    "ORDER BY created_at DESC",
                    (str(scope_owner_id),),
                ).fetchall()
            return [self._decode(row[0]) for row in rows]

    def get(
        self,
        task_id: str,
        scope_owner_id: Optional[str] = None,
        include_unowned: bool = False,
    ) -> Optional[dict]:
        with self._lock, self._connect() as connection:
            if scope_owner_id is None:
                row = connection.execute(
                    "SELECT document FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
            elif include_unowned:
                row = connection.execute(
                    "SELECT document FROM tasks WHERE id = ? "
                    "AND (owner_id = ? OR owner_id = '')",
                    (task_id, str(scope_owner_id)),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT document FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, str(scope_owner_id)),
                ).fetchone()
            return self._decode(row[0]) if row else None

    def get_or_create_workspace_id(self, preferred_id: str = "") -> str:
        """Return one stable local workspace identity across sessions/processes."""
        with self._lock, self._transaction() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'workspace_id'"
            ).fetchone()
            if row and row[0]:
                return row[0]
            workspace_id = str(preferred_id or "").strip() or str(uuid.uuid4())
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES('workspace_id', ?)",
                (workspace_id,),
            )
            return workspace_id

    def get_metadata(self, key: str, default: str = "") -> str:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?", (str(key),)
            ).fetchone()
            return row[0] if row else default

    def set_metadata(self, key: str, value: str) -> None:
        with self._lock, self._transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) VALUES(?, ?)",
                (str(key), str(value)),
            )

    def create(self, task: dict, max_tasks: int, terminal_statuses: Iterable[str]) -> dict:
        terminal = tuple(sorted(set(terminal_statuses)))
        owner_id = str(task.get("owner_id") or "")
        with self._lock, self._transaction() as connection:
            if owner_id:
                count = connection.execute(
                    "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
                ).fetchone()[0]
            else:
                count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            while count >= max_tasks:
                placeholders = ",".join("?" for _ in terminal)
                if owner_id:
                    rows = connection.execute(
                        f"SELECT id, document FROM tasks WHERE status IN ({placeholders}) "
                        "AND owner_id = ? ORDER BY created_at ASC",
                        terminal + (owner_id,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        f"SELECT id, document FROM tasks WHERE status IN ({placeholders}) "
                        "ORDER BY created_at ASC",
                        terminal,
                    ).fetchall()
                row = next(
                    (
                        candidate
                        for candidate in rows
                        if self._decode(candidate[1]).get("history_archived_at")
                    ),
                    None,
                )
                if not row:
                    raise TaskCapacityError("task queue is full")
                connection.execute("DELETE FROM tasks WHERE id = ?", (row[0],))
                count -= 1
            self._insert(connection, copy.deepcopy(task))
            return copy.deepcopy(task)

    def update(
        self,
        task_id: str,
        updates: dict,
        expected_status: Optional[Union[str, Iterable[str]]] = None,
        expected_claim_token: Optional[str] = None,
        scope_owner_id: Optional[str] = None,
        include_unowned: bool = False,
    ) -> Optional[dict]:
        with self._lock, self._transaction() as connection:
            if scope_owner_id is None:
                row = connection.execute(
                    "SELECT status, document FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
            elif include_unowned:
                row = connection.execute(
                    "SELECT status, document FROM tasks WHERE id = ? "
                    "AND (owner_id = ? OR owner_id = '')",
                    (task_id, str(scope_owner_id)),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT status, document FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, str(scope_owner_id)),
                ).fetchone()
            if not row or not self._status_matches(row[0], expected_status):
                return None
            task = self._decode(row[1])
            if (
                expected_claim_token is not None
                and task.get("claim_token") != expected_claim_token
            ):
                return None
            next_status = updates.get("status", row[0])
            if not self._transition_allowed(row[0], next_status):
                return None
            task.update(copy.deepcopy(updates))
            self._replace(connection, task)
            return copy.deepcopy(task)

    def claim_next(
        self,
        max_running: int,
        runner_id: str,
        now: Optional[datetime] = None,
        lease_seconds: int = DEFAULT_RUNNER_LEASE_SECONDS,
    ) -> Optional[dict]:
        """Atomically claim the oldest queued task within the global run limit."""
        if max_running <= 0:
            return None
        current = now or datetime.now()
        timestamp = current.isoformat()
        available_timestamp = _normalize_available_at(current)
        lease_expires_at = (
            current + timedelta(seconds=max(5, int(lease_seconds)))
        ).isoformat()
        with self._lock, self._transaction() as connection:
            self._heartbeat_runner(
                connection, runner_id, timestamp, lease_expires_at
            )
            running_count = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = 'running'"
            ).fetchone()[0]
            if running_count >= max_running:
                return None
            row = connection.execute(
                "SELECT document FROM tasks WHERE status = 'queued' "
                "AND (available_at = '' OR available_at <= ?) "
                "ORDER BY priority DESC, created_at ASC, id ASC LIMIT 1",
                (available_timestamp,),
            ).fetchone()
            if not row:
                return None
            task = self._decode(row[0])
            task.update(
                {
                    "status": "running",
                    "runner_id": runner_id,
                    "claim_token": uuid.uuid4().hex,
                    "runner_lease_expires_at": lease_expires_at,
                    "started_at": task.get("started_at") or timestamp,
                    "updated_at": timestamp,
                }
            )
            self._replace(connection, task)
            return copy.deepcopy(task)

    def heartbeat_runner(
        self,
        runner_id: str,
        lease_seconds: int = DEFAULT_RUNNER_LEASE_SECONDS,
        now: Optional[datetime] = None,
    ) -> str:
        current = now or datetime.now()
        heartbeat_at = current.isoformat()
        lease_expires_at = (
            current + timedelta(seconds=max(5, int(lease_seconds)))
        ).isoformat()
        with self._lock, self._transaction() as connection:
            self._heartbeat_runner(
                connection, runner_id, heartbeat_at, lease_expires_at
            )
        return lease_expires_at

    def clear_terminal(
        self,
        terminal_statuses: Iterable[str],
        scope_owner_id: Optional[str] = None,
        include_unowned: bool = False,
    ) -> int:
        terminal = tuple(sorted(set(terminal_statuses)))
        if not terminal:
            return 0
        placeholders = ",".join("?" for _ in terminal)
        with self._lock, self._transaction() as connection:
            if scope_owner_id is None:
                cursor = connection.execute(
                    f"DELETE FROM tasks WHERE status IN ({placeholders})", terminal
                )
            elif include_unowned:
                cursor = connection.execute(
                    f"DELETE FROM tasks WHERE status IN ({placeholders}) "
                    "AND (owner_id = ? OR owner_id = '')",
                    terminal + (str(scope_owner_id),),
                )
            else:
                cursor = connection.execute(
                    f"DELETE FROM tasks WHERE status IN ({placeholders}) "
                    "AND owner_id = ?",
                    terminal + (str(scope_owner_id),),
                )
            return cursor.rowcount

    def clear_archived_done(
        self,
        scope_owner_id: Optional[str] = None,
        include_unowned: bool = False,
    ) -> int:
        """Remove only completed tasks whose history has been archived."""
        with self._lock, self._transaction() as connection:
            if scope_owner_id is None:
                rows = connection.execute(
                    "SELECT id, document FROM tasks WHERE status = 'done'"
                ).fetchall()
            elif include_unowned:
                rows = connection.execute(
                    "SELECT id, document FROM tasks WHERE status = 'done' "
                    "AND (owner_id = ? OR owner_id = '')",
                    (str(scope_owner_id),),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT id, document FROM tasks WHERE status = 'done' "
                    "AND owner_id = ?",
                    (str(scope_owner_id),),
                ).fetchall()
            archived_ids = []
            for task_id, document in rows:
                try:
                    task = self._decode(document)
                except (TypeError, ValueError):
                    continue
                if isinstance(task, dict) and task.get("history_archived_at"):
                    archived_ids.append((task_id,))
            connection.executemany(
                "DELETE FROM tasks WHERE id = ?", archived_ids
            )
            return len(archived_ids)

    def recover_orphaned_running(
        self,
        active_task_ids: Iterable[str],
        error_message: str,
        now: Optional[datetime] = None,
        runner_id: Optional[str] = None,
    ) -> list:
        active = set(active_task_ids)
        timestamp = (now or datetime.now()).isoformat()
        recovered = []
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                "SELECT id, document FROM tasks WHERE status = 'running'"
            ).fetchall()
            runner_leases = {
                row[0]: row[1]
                for row in connection.execute(
                    "SELECT id, lease_expires_at FROM task_runners"
                ).fetchall()
            }
            for task_id, document in rows:
                if task_id in active:
                    continue
                task = self._decode(document)
                task_runner_id = str(task.get("runner_id") or "")
                if runner_id and task_runner_id and task_runner_id != runner_id:
                    lease_expires_at = runner_leases.get(task_runner_id, "")
                    if lease_expires_at and lease_expires_at > timestamp:
                        continue
                task["status"] = "expired"
                errors = list(task.get("errors") or [])
                errors.append(error_message)
                task["errors"] = errors
                task["updated_at"] = timestamp
                task["ended_at"] = task.get("ended_at") or timestamp
                self._replace(connection, task)
                recovered.append(copy.deepcopy(task))
        return recovered

    def migrate(self, transform: Callable[[dict], dict]) -> bool:
        with self._lock, self._transaction() as connection:
            rows = connection.execute(
                "SELECT document FROM tasks ORDER BY created_at ASC"
            ).fetchall()
            current = {
                "schema_version": SCHEMA_VERSION,
                "tasks": [self._decode(row[0]) for row in rows],
            }
            migrated = transform(copy.deepcopy(current))
            if migrated == current:
                return False
            connection.execute("DELETE FROM tasks")
            for task in migrated.get("tasks", []):
                self._insert(connection, task)
            return True

    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _transaction(self):
        return _ImmediateTransaction(self._connect())

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
        with self._lock, self._transaction() as connection:
            self._create_base_schema(connection)
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            current_version = int(row[0]) if row else 1
            if current_version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"task database schema {current_version} is newer than supported {SCHEMA_VERSION}"
                )
            if not row:
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES('schema_version', '1')"
                )
            for target_version in range(current_version + 1, SCHEMA_VERSION + 1):
                self._apply_schema_migration(connection, target_version)
                connection.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'schema_version'",
                    (str(target_version),),
                )
            self._normalize_available_at_columns(connection)

    @staticmethod
    def _create_base_schema(connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS metadata ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id TEXT PRIMARY KEY, "
            "task_type TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "owner_id TEXT NOT NULL DEFAULT '', "
            "created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL, "
            "document TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS task_runners ("
            "id TEXT PRIMARY KEY, "
            "heartbeat_at TEXT NOT NULL, "
            "lease_expires_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_status_created "
            "ON tasks(status, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_owner_created "
            "ON tasks(owner_id, created_at DESC)"
        )

    @staticmethod
    def _apply_schema_migration(connection, target_version: int) -> None:
        if target_version != 2:
            raise RuntimeError(f"missing task database migration to v{target_version}")
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "priority" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
            )
        if "available_at" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN available_at TEXT NOT NULL DEFAULT ''"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_claim_order "
            "ON tasks(status, priority DESC, available_at, created_at, id)"
        )

    @staticmethod
    def _normalize_available_at_columns(connection) -> None:
        rows = connection.execute(
            "SELECT id, available_at, document FROM tasks"
        ).fetchall()
        for task_id, indexed_value, document in rows:
            try:
                task = json.loads(document)
            except (TypeError, ValueError):
                task = None
            if not isinstance(task, dict):
                if indexed_value != INVALID_AVAILABLE_AT_SENTINEL:
                    connection.execute(
                        "UPDATE tasks SET available_at = ? WHERE id = ?",
                        (INVALID_AVAILABLE_AT_SENTINEL, task_id),
                    )
                continue
            try:
                normalized = _normalize_available_at(task.get("available_at"))
            except ValueError:
                normalized = INVALID_AVAILABLE_AT_SENTINEL
                task["available_at"] = normalized
                document = json.dumps(task, ensure_ascii=False, separators=(",", ":"))
            if indexed_value != normalized:
                connection.execute(
                    "UPDATE tasks SET available_at = ?, document = ? WHERE id = ?",
                    (normalized, document, task_id),
                )

    def _migrate_legacy_json(self) -> None:
        if not self.legacy_json_path or not self.legacy_json_path.exists():
            return
        with self._lock, self._transaction() as connection:
            migrated = connection.execute(
                "SELECT value FROM metadata WHERE key = 'legacy_json_migrated'"
            ).fetchone()
            if migrated and migrated[0] == "1":
                return
            if connection.execute("SELECT 1 FROM tasks LIMIT 1").fetchone():
                connection.execute(
                    "INSERT OR REPLACE INTO metadata(key, value) "
                    "VALUES('legacy_json_migrated', '1')"
                )
                return
            try:
                data = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return
            for task in data.get("tasks", []) if isinstance(data, dict) else []:
                if isinstance(task, dict) and task.get("id"):
                    legacy_task = copy.deepcopy(task)
                    try:
                        _normalize_available_at(legacy_task.get("available_at"))
                    except ValueError:
                        legacy_task["available_at"] = INVALID_AVAILABLE_AT_SENTINEL
                    self._insert(connection, legacy_task)
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value) "
                "VALUES('legacy_json_migrated', '1')"
            )

    def _insert(self, connection, task: dict) -> None:
        connection.execute(
            "INSERT INTO tasks(id, task_type, status, owner_id, priority, available_at, "
            "created_at, updated_at, document) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            self._columns(task),
        )

    @staticmethod
    def _heartbeat_runner(
        connection,
        runner_id: str,
        heartbeat_at: str,
        lease_expires_at: str,
    ) -> None:
        normalized_runner_id = str(runner_id or "").strip()
        if not normalized_runner_id:
            raise ValueError("runner id is required")
        connection.execute(
            "INSERT INTO task_runners(id, heartbeat_at, lease_expires_at) "
            "VALUES(?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET heartbeat_at = excluded.heartbeat_at, "
            "lease_expires_at = excluded.lease_expires_at",
            (normalized_runner_id, heartbeat_at, lease_expires_at),
        )

    def _replace(self, connection, task: dict) -> None:
        connection.execute(
            "UPDATE tasks SET task_type = ?, status = ?, owner_id = ?, priority = ?, "
            "available_at = ?, created_at = ?, updated_at = ?, document = ? WHERE id = ?",
            self._columns(task)[1:] + (task.get("id", ""),),
        )

    @staticmethod
    def _columns(task: dict) -> tuple:
        task_id = str(task.get("id") or "")
        if not task_id:
            raise ValueError("task id is required")
        return (
            task_id,
            str(task.get("type") or "task"),
            str(task.get("status") or "queued"),
            str(task.get("owner_id") or ""),
            int(task.get("priority") or 0),
            _normalize_available_at(task.get("available_at")),
            str(task.get("created_at") or ""),
            str(task.get("updated_at") or ""),
            json.dumps(task, ensure_ascii=False, separators=(",", ":")),
        )

    @staticmethod
    def _decode(document: str) -> dict:
        return json.loads(document)

    @staticmethod
    def _status_matches(
        current_status: str,
        expected_status: Optional[Union[str, Iterable[str]]],
    ) -> bool:
        if expected_status is None:
            return True
        if isinstance(expected_status, str):
            return current_status == expected_status
        return current_status in set(expected_status)

    @staticmethod
    def _transition_allowed(current_status: str, next_status: str) -> bool:
        if current_status == next_status:
            return True
        return next_status in TASK_STATUS_TRANSITIONS.get(current_status, set())


class _ImmediateTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.execute("BEGIN IMMEDIATE")
        return self.connection

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()
        return False
