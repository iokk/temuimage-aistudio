from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from itertools import count
import os
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.db.models import Job
from apps.api.db.models import User


TASK_TYPE_META = {
    "title_generation": {"title": "标题优化", "page": "标题优化", "icon": "Aa"},
    "image_translate": {"title": "图片翻译", "page": "图片翻译", "icon": "⇄"},
    "quick_generation": {"title": "快速出图", "page": "快速出图", "icon": "⇢"},
    "batch_generation": {"title": "批量出图", "page": "批量出图", "icon": "▥"},
}

TIMELINE_KEY = "_timeline"

_memory_counter = count(1)
_memory_jobs: list[dict[str, Any]] = []
SYSTEM_USER_ID = "system"
SYSTEM_USER_EMAIL = "system@xiaobaitu.local"


def build_task_meta(task_type: str) -> dict[str, str]:
    return TASK_TYPE_META.get(
        task_type, {"title": "任务", "page": "工作台", "icon": "●"}
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_status_message(status: str) -> str:
    return {
        "queued": "任务已进入队列",
        "running": "任务开始执行",
        "completed": "任务执行完成",
        "failed": "任务执行失败",
    }.get(status, f"任务状态更新为 {status}")


def _build_timeline_entry(
    status: str, result: dict[str, Any] | None = None
) -> dict[str, str]:
    message = _default_status_message(status)
    if status == "failed" and isinstance(result, dict) and result.get("error"):
        message = str(result["error"])
    return {
        "status": status,
        "at": _now_iso(),
        "message": message,
    }


def _extract_public_result(result: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not isinstance(result, dict):
        return {}, []

    timeline = result.get(TIMELINE_KEY)
    public_result = {key: value for key, value in result.items() if key != TIMELINE_KEY}
    return public_result, timeline if isinstance(timeline, list) else []


def _pack_result_with_timeline(
    result: dict[str, Any] | None,
    timeline: list[dict[str, str]],
) -> dict[str, Any]:
    public_result = dict(result or {})
    public_result[TIMELINE_KEY] = timeline
    return public_result


def _normalize_job_record(job: Job | dict[str, Any]) -> dict[str, Any]:
    if isinstance(job, dict):
        return job

    meta = build_task_meta(job.type)
    created_at = job.created_at.isoformat() if job.created_at else _now_iso()
    updated_at = job.updated_at.isoformat() if job.updated_at else created_at
    public_result, history = _extract_public_result(job.result or {})
    return {
        "id": job.id,
        "task_type": job.type,
        "status": job.status,
        "summary": str((job.payload or {}).get("summary") or meta["title"]),
        "page": meta["page"],
        "title": meta["title"],
        "icon": meta["icon"],
        "payload": job.payload or {},
        "result": public_result,
        "created_at": created_at,
        "updated_at": updated_at,
        "history": history,
    }


class MemoryJobRepository:
    backend_name = "memory"

    def create_job(
        self,
        *,
        task_type: str,
        summary: str,
        status: str,
        payload: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = build_task_meta(task_type)
        now_iso = _now_iso()
        history = [_build_timeline_entry(status, result)]
        job = {
            "id": f"job-{next(_memory_counter)}",
            "task_type": task_type,
            "status": status,
            "summary": summary,
            "page": meta["page"],
            "title": meta["title"],
            "icon": meta["icon"],
            "payload": payload,
            "result": result or {},
            "created_at": now_iso,
            "updated_at": now_iso,
            "history": history,
        }
        _memory_jobs.insert(0, job)
        del _memory_jobs[50:]
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        return list(_memory_jobs)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        for job in _memory_jobs:
            if job.get("id") == job_id:
                return dict(job)
        return None

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        for index, job in enumerate(_memory_jobs):
            if job.get("id") != job_id:
                continue
            history = list(job.get("history") or [])
            history.append(_build_timeline_entry(status, result))
            updated = {
                **job,
                "status": status,
                "result": result if result is not None else job.get("result") or {},
                "updated_at": _now_iso(),
                "history": history,
            }
            _memory_jobs[index] = updated
            return dict(updated)
        return None

    def count_pending_jobs(self) -> int:
        return sum(
            1 for job in _memory_jobs if job.get("status") in {"queued", "running"}
        )

    def get_backend_meta(self) -> dict[str, Any]:
        return {
            "active_backend": self.backend_name,
            "preferred_backend": self.backend_name,
            "fallback_reason": "",
            "persistence_ready": False,
        }


class SqlAlchemyJobRepository:
    backend_name = "database"

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @contextmanager
    def _session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _ensure_system_user(self, session: Session) -> None:
        row = session.get(User, SYSTEM_USER_ID)
        if row:
            return
        session.add(
            User(
                id=SYSTEM_USER_ID,
                email=SYSTEM_USER_EMAIL,
                name="System",
                mode="personal",
            )
        )
        session.commit()

    def create_job(
        self,
        *,
        task_type: str,
        summary: str,
        status: str,
        payload: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record_id = f"job_{uuid4().hex}"
        history = [_build_timeline_entry(status, result)]
        with self._session() as session:
            owner_id = str(payload.get("ownerId") or SYSTEM_USER_ID)
            if owner_id == SYSTEM_USER_ID:
                self._ensure_system_user(session)
            job = Job(
                id=record_id,
                type=task_type,
                status=status,
                owner_id=owner_id,
                payload={**payload, "summary": summary},
                result=_pack_result_with_timeline(result, history),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return _normalize_job_record(job)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._session() as session:
            rows = (
                session.execute(select(Job).order_by(Job.created_at.desc()).limit(50))
                .scalars()
                .all()
            )
            return [_normalize_job_record(row) for row in rows]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Job, job_id)
            if not row:
                return None
            return _normalize_job_record(row)

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Job, job_id)
            if not row:
                return None
            current_result, history = _extract_public_result(row.result or {})
            next_result = result if result is not None else current_result
            history.append(_build_timeline_entry(status, result))
            row.status = status
            row.result = _pack_result_with_timeline(next_result, history)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _normalize_job_record(row)

    def count_pending_jobs(self) -> int:
        return sum(
            1 for job in self.list_jobs() if job.get("status") in {"queued", "running"}
        )

    def get_backend_meta(self) -> dict[str, Any]:
        return {
            "active_backend": self.backend_name,
            "preferred_backend": self.backend_name,
            "fallback_reason": "",
            "persistence_ready": True,
        }


class ResilientJobRepository:
    def __init__(
        self,
        *,
        preferred_backend: str,
        primary: SqlAlchemyJobRepository | MemoryJobRepository,
        fallback: MemoryJobRepository,
    ):
        self._preferred_backend = preferred_backend
        self._primary = primary
        self._fallback = fallback
        self._fallback_reason = ""
        self._using_fallback = False

    def _with_fallback(self, operation: str, func: Callable[[], Any]):
        if self._using_fallback:
            return getattr(self._fallback, operation)()

        try:
            return func()
        except Exception as exc:  # pragma: no cover - defensive fallback path
            self._using_fallback = True
            self._fallback_reason = str(exc)
            return getattr(self._fallback, operation)()

    def create_job(self, **kwargs):
        return self._with_fallback(
            "create_job",
            lambda: self._primary.create_job(**kwargs),
        )

    def list_jobs(self):
        return self._with_fallback("list_jobs", self._primary.list_jobs)

    def count_pending_jobs(self):
        return self._with_fallback(
            "count_pending_jobs",
            self._primary.count_pending_jobs,
        )

    def get_job(self, job_id: str):
        return self._with_fallback(
            "get_job",
            lambda: self._primary.get_job(job_id),
        )

    def update_job(self, job_id: str, **kwargs):
        return self._with_fallback(
            "update_job",
            lambda: self._primary.update_job(job_id, **kwargs),
        )

    def get_backend_meta(self) -> dict[str, Any]:
        active_backend = "memory" if self._using_fallback else self._preferred_backend
        return {
            "active_backend": active_backend,
            "preferred_backend": self._preferred_backend,
            "fallback_reason": self._fallback_reason,
            "persistence_ready": active_backend == "database",
        }


def build_job_repository():
    backend = os.getenv("JOB_STORE_BACKEND", "memory").strip().lower()
    database_url = os.getenv("DATABASE_URL", "").strip()
    fallback = MemoryJobRepository()

    if backend == "database" and database_url:
        try:
            engine = create_engine(database_url, future=True)
            session_factory = sessionmaker(
                bind=engine, autoflush=False, autocommit=False
            )
            return ResilientJobRepository(
                preferred_backend="database",
                primary=SqlAlchemyJobRepository(session_factory),
                fallback=fallback,
            )
        except (ModuleNotFoundError, SQLAlchemyError, ValueError):
            repository = ResilientJobRepository(
                preferred_backend="database",
                primary=fallback,
                fallback=fallback,
            )
            repository._using_fallback = True
            repository._fallback_reason = "Database backend initialization failed"
            return repository

    return fallback


job_repository = build_job_repository()
