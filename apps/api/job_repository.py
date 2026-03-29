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

    def upsert_user(
        self,
        *,
        user_id: str,
        email: str,
        name: str,
        issuer: str,
        subject: str,
        email_verified: bool,
        last_login_at: datetime,
    ) -> dict[str, Any]:
        return {
            "id": user_id,
            "email": email,
            "name": name,
            "issuer": issuer,
            "subject": subject,
            "email_verified": email_verified,
            "last_login_at": last_login_at.isoformat(),
        }

    def create_job(
        self,
        *,
        task_type: str,
        summary: str,
        status: str,
        payload: dict[str, Any],
        owner_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        meta = build_task_meta(task_type)
        now_iso = _now_iso()
        history = [_build_timeline_entry(status, result)]
        job = {
            "id": f"job-{next(_memory_counter)}",
            "owner_id": owner_id or SYSTEM_USER_ID,
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

    def list_jobs(
        self,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        if include_all or owner_id is None:
            return list(_memory_jobs)
        return [job for job in _memory_jobs if job.get("owner_id") == owner_id]

    def get_job(
        self,
        job_id: str,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
    ) -> dict[str, Any] | None:
        for job in _memory_jobs:
            if job.get("id") == job_id:
                if not include_all and owner_id and job.get("owner_id") != owner_id:
                    return None
                return dict(job)
        return None

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        owner_id: str | None = None,
        include_all: bool = False,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        for index, job in enumerate(_memory_jobs):
            if job.get("id") != job_id:
                continue
            if not include_all and owner_id and job.get("owner_id") != owner_id:
                return None
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

    def count_pending_jobs(
        self,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
    ) -> int:
        return sum(
            1
            for job in self.list_jobs(owner_id=owner_id, include_all=include_all)
            if job.get("status") in {"queued", "running"}
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
                issuer="internal",
                subject="system",
                email_verified=True,
            )
        )
        session.commit()

    def upsert_user(
        self,
        *,
        user_id: str,
        email: str,
        name: str,
        issuer: str,
        subject: str,
        email_verified: bool,
        last_login_at: datetime,
    ) -> dict[str, Any]:
        with self._session() as session:
            row = session.execute(
                select(User).where(User.issuer == issuer, User.subject == subject)
            ).scalar_one_or_none()

            if row is None and email:
                row = session.execute(
                    select(User).where(User.email == email)
                ).scalar_one_or_none()

            if row is None:
                row = User(
                    id=user_id,
                    email=email,
                    name=name or email,
                    mode="personal",
                    issuer=issuer,
                    subject=subject,
                    email_verified=email_verified,
                    last_login_at=last_login_at,
                )
            else:
                row.email = email
                row.name = name or row.name or email
                row.issuer = issuer
                row.subject = subject
                row.email_verified = email_verified
                row.last_login_at = last_login_at

            session.add(row)
            session.commit()
            session.refresh(row)
            return {
                "id": row.id,
                "email": row.email,
                "issuer": row.issuer,
                "subject": row.subject,
            }

    def create_job(
        self,
        *,
        task_type: str,
        summary: str,
        status: str,
        payload: dict[str, Any],
        owner_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record_id = f"job_{uuid4().hex}"
        history = [_build_timeline_entry(status, result)]
        with self._session() as session:
            resolved_owner_id = str(
                owner_id or payload.get("ownerId") or SYSTEM_USER_ID
            )
            if resolved_owner_id == SYSTEM_USER_ID:
                self._ensure_system_user(session)
            elif not session.get(User, resolved_owner_id):
                raise ValueError("Job owner does not exist")
            job = Job(
                id=record_id,
                type=task_type,
                status=status,
                owner_id=resolved_owner_id,
                payload={**payload, "summary": summary},
                result=_pack_result_with_timeline(result, history),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return _normalize_job_record(job)

    def list_jobs(
        self,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            statement = select(Job)
            if not include_all and owner_id:
                statement = statement.where(Job.owner_id == owner_id)
            rows = (
                session.execute(statement.order_by(Job.created_at.desc()).limit(50))
                .scalars()
                .all()
            )
            return [_normalize_job_record(row) for row in rows]

    def get_job(
        self,
        job_id: str,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
    ) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Job, job_id)
            if not row:
                return None
            if not include_all and owner_id and row.owner_id != owner_id:
                return None
            return _normalize_job_record(row)

    def update_job(
        self,
        job_id: str,
        *,
        status: str,
        owner_id: str | None = None,
        include_all: bool = False,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(Job, job_id)
            if not row:
                return None
            if not include_all and owner_id and row.owner_id != owner_id:
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

    def count_pending_jobs(
        self,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
    ) -> int:
        return sum(
            1
            for job in self.list_jobs(owner_id=owner_id, include_all=include_all)
            if job.get("status") in {"queued", "running"}
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

    def upsert_user(self, **kwargs):
        return self._with_fallback(
            "upsert_user",
            lambda: self._primary.upsert_user(**kwargs),
        )

    def list_jobs(self, **kwargs):
        return self._with_fallback(
            "list_jobs",
            lambda: self._primary.list_jobs(**kwargs),
        )

    def count_pending_jobs(self, **kwargs):
        return self._with_fallback(
            "count_pending_jobs",
            lambda: self._primary.count_pending_jobs(**kwargs),
        )

    def get_job(self, job_id: str, **kwargs):
        return self._with_fallback(
            "get_job",
            lambda: self._primary.get_job(job_id, **kwargs),
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
