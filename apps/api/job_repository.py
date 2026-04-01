from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone
from itertools import count
import os
import re
from typing import Any
from uuid import uuid4

try:
    from sqlalchemy import create_engine, select
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session, sessionmaker
except ModuleNotFoundError:  # pragma: no cover - optional local dependency

    def _missing_sqlalchemy(*args: Any, **kwargs: Any) -> Any:
        raise ModuleNotFoundError("sqlalchemy is not installed")

    create_engine = _missing_sqlalchemy
    select = _missing_sqlalchemy
    sessionmaker = _missing_sqlalchemy
    Session = Any

    class SQLAlchemyError(Exception):
        pass


from apps.api.db.models import Job
from apps.api.db.models import Membership
from apps.api.db.models import Organization
from apps.api.db.models import Project
from apps.api.db.models import User
from temu_core.settings import normalize_database_url


TASK_TYPE_META = {
    "title_generation": {"title": "标题优化", "page": "标题优化", "icon": "Aa"},
    "image_translate": {"title": "图片翻译", "page": "图片翻译", "icon": "⇄"},
    "quick_generation": {"title": "快速出图", "page": "快速出图", "icon": "⇢"},
    "batch_generation": {"title": "批量出图", "page": "批量出图", "icon": "▥"},
}

TIMELINE_KEY = "_timeline"

_memory_counter = count(1)
_memory_jobs: list[dict[str, Any]] = []
_memory_users: dict[str, dict[str, Any]] = {}
_memory_organizations: dict[str, dict[str, Any]] = {}
_memory_memberships: list[dict[str, Any]] = []
_memory_projects: dict[str, dict[str, Any]] = {}
SYSTEM_USER_ID = "system"
SYSTEM_USER_EMAIL = "system@xiaobaitu.local"
DEFAULT_TEAM_ORGANIZATION_ID = "org_xiaobaitu_team"
DEFAULT_TEAM_ORGANIZATION_NAME = "XiaoBaiTu Team"
DEFAULT_TEAM_ORGANIZATION_SLUG = "xiaobaitu-team"
DEFAULT_PROJECT_ID = "project_xiaobaitu_default"
DEFAULT_PROJECT_NAME = "Default Workspace"
DEFAULT_PROJECT_SLUG = "default-workspace"
PERSONAL_WORKSPACE_NAME = "Personal Workspace"


def _personal_suffix(user_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(user_id).strip().lower()).strip("-") or "user"


def _build_personal_organization_id(user_id: str) -> str:
    return f"org_personal_{_personal_suffix(user_id)}"


def _build_personal_organization_slug(user_id: str) -> str:
    return f"personal-account-{_personal_suffix(user_id)}"


def _build_personal_project_id(user_id: str) -> str:
    return f"project_personal_{_personal_suffix(user_id)}"


def _build_personal_project_slug(user_id: str) -> str:
    return f"personal-workspace-{_personal_suffix(user_id)}"


def _prefer_membership(
    memberships: list[dict[str, Any]], *, prefer_personal: bool = False
) -> dict[str, Any] | None:
    if not memberships:
        return None
    if prefer_personal:
        return next(
            (item for item in memberships if str(item.get("role") or "") == "personal"),
            memberships[0],
        )
    return next(
        (item for item in memberships if str(item.get("role") or "") != "personal"),
        memberships[0],
    )


def _slugify_project_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")
    return slug or f"project-{uuid4().hex[:8]}"


def _serialize_project(project: dict[str, Any] | None) -> dict[str, Any] | None:
    if not project:
        return None
    return {
        "project_id": str(project.get("id") or ""),
        "project_name": str(project.get("name") or ""),
        "project_slug": str(project.get("slug") or ""),
        "project_status": str(project.get("status") or "active"),
    }


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
        record = dict(job)
        record["project"] = _extract_project_meta(record)
        return record

    meta = build_task_meta(job.type)
    created_at = job.created_at.isoformat() if job.created_at else _now_iso()
    updated_at = job.updated_at.isoformat() if job.updated_at else created_at
    public_result, history = _extract_public_result(job.result or {})
    return {
        "id": job.id,
        "task_type": job.type,
        "status": job.status,
        "project_id": getattr(job, "project_id", None),
        "summary": str((job.payload or {}).get("summary") or meta["title"]),
        "page": meta["page"],
        "title": meta["title"],
        "icon": meta["icon"],
        "payload": job.payload or {},
        "result": public_result,
        "created_at": created_at,
        "updated_at": updated_at,
        "history": history,
        "project": _extract_project_meta(
            {
                "project_id": getattr(job, "project_id", None),
                "payload": job.payload or {},
            }
        ),
    }


def _build_job_list_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record.get("id") or ""),
        "status": str(record.get("status") or "queued"),
        "summary": str(record.get("summary") or ""),
        "title": str(record.get("title") or "任务"),
        "icon": str(record.get("icon") or "●"),
        "created_at": str(record.get("created_at") or _now_iso()),
        "project": record.get("project"),
    }


def _extract_project_meta(record: dict[str, Any]) -> dict[str, Any] | None:
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    project_id = str(
        record.get("project_id") or (payload or {}).get("projectId") or ""
    ).strip()
    project_name = str((payload or {}).get("projectName") or "").strip()
    project_slug = str((payload or {}).get("projectSlug") or "").strip()
    if not (project_id or project_name or project_slug):
        return None
    return {
        "project_id": project_id,
        "project_name": project_name,
        "project_slug": project_slug,
        "project_status": "active",
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
        record = {
            "id": user_id,
            "email": email,
            "name": name,
            "mode": "personal",
            "issuer": issuer,
            "subject": subject,
            "email_verified": email_verified,
            "last_login_at": last_login_at.isoformat(),
        }
        _memory_users[user_id] = record
        return record

    def ensure_team_state(
        self,
        *,
        user_id: str,
        is_admin: bool,
    ) -> dict[str, Any]:
        user = _memory_users.get(user_id)
        if user is None:
            raise ValueError("User does not exist")
        user["mode"] = "team"

        organization = _memory_organizations.get(DEFAULT_TEAM_ORGANIZATION_ID)
        if organization is None:
            organization = {
                "id": DEFAULT_TEAM_ORGANIZATION_ID,
                "name": DEFAULT_TEAM_ORGANIZATION_NAME,
                "slug": DEFAULT_TEAM_ORGANIZATION_SLUG,
            }
            _memory_organizations[DEFAULT_TEAM_ORGANIZATION_ID] = organization

        membership = next(
            (
                item
                for item in _memory_memberships
                if item.get("user_id") == user_id
                and item.get("organization_id") == DEFAULT_TEAM_ORGANIZATION_ID
            ),
            None,
        )
        if membership is None:
            membership = {
                "id": f"membership-{user_id}-{DEFAULT_TEAM_ORGANIZATION_ID}",
                "user_id": user_id,
                "organization_id": DEFAULT_TEAM_ORGANIZATION_ID,
                "active_project_id": None,
                "role": "admin" if is_admin else "member",
            }
            _memory_memberships.append(membership)
        else:
            membership["role"] = "admin" if is_admin else "member"

        self.ensure_project_state(user_id=user_id)
        return self.get_account_team_state(user_id=user_id)

    def ensure_personal_state(self, *, user_id: str) -> dict[str, Any]:
        user = _memory_users.get(user_id)
        if user is None:
            raise ValueError("User does not exist")

        user["mode"] = "personal"
        organization_id = _build_personal_organization_id(user_id)
        organization = _memory_organizations.get(organization_id)
        if organization is None:
            organization = {
                "id": organization_id,
                "name": PERSONAL_WORKSPACE_NAME,
                "slug": _build_personal_organization_slug(user_id),
            }
            _memory_organizations[organization_id] = organization

        membership = next(
            (
                item
                for item in _memory_memberships
                if item.get("user_id") == user_id
                and item.get("organization_id") == organization_id
            ),
            None,
        )
        if membership is None:
            membership = {
                "id": f"membership-{user_id}-{organization_id}",
                "user_id": user_id,
                "organization_id": organization_id,
                "active_project_id": None,
                "role": "personal",
            }
            _memory_memberships.append(membership)
        else:
            membership["role"] = "personal"

        self.ensure_project_state(user_id=user_id)
        return self.get_account_team_state(user_id=user_id)

    def _select_membership(self, *, user_id: str) -> dict[str, Any] | None:
        user = _memory_users.get(user_id) or {}
        memberships = [
            item for item in _memory_memberships if item.get("user_id") == user_id
        ]
        return _prefer_membership(
            memberships,
            prefer_personal=str(user.get("mode") or "") == "personal",
        )

    def ensure_project_state(self, *, user_id: str) -> dict[str, Any]:
        membership = self._select_membership(user_id=user_id)
        organization_id = str(
            (membership or {}).get("organization_id") or DEFAULT_TEAM_ORGANIZATION_ID
        )
        organization = _memory_organizations.get(organization_id)
        if organization is None:
            organization = {
                "id": organization_id,
                "name": DEFAULT_TEAM_ORGANIZATION_NAME,
                "slug": DEFAULT_TEAM_ORGANIZATION_SLUG,
            }
            _memory_organizations[organization_id] = organization

        is_personal = str((membership or {}).get("role") or "") == "personal"
        project_id = (
            _build_personal_project_id(user_id) if is_personal else DEFAULT_PROJECT_ID
        )
        project_name = PERSONAL_WORKSPACE_NAME if is_personal else DEFAULT_PROJECT_NAME
        project_slug = (
            _build_personal_project_slug(user_id)
            if is_personal
            else DEFAULT_PROJECT_SLUG
        )
        project = _memory_projects.get(project_id)
        if project is None:
            project = {
                "id": project_id,
                "organization_id": organization_id,
                "name": project_name,
                "slug": project_slug,
                "status": "active",
            }
            _memory_projects[project_id] = project
        if membership is not None and not membership.get("active_project_id"):
            membership["active_project_id"] = project_id

        return self.get_account_team_state(user_id=user_id)

    def get_account_team_state(self, *, user_id: str) -> dict[str, Any]:
        user = dict(_memory_users.get(user_id) or {})
        membership = self._select_membership(user_id=user_id)
        organization = (
            _memory_organizations.get(str(membership.get("organization_id") or ""))
            if membership
            else None
        )
        is_personal = str((membership or {}).get("role") or "") == "personal"
        fallback_project_id = (
            _build_personal_project_id(user_id) if is_personal else DEFAULT_PROJECT_ID
        )
        current_project_id = str((membership or {}).get("active_project_id") or "")
        current_project = _memory_projects.get(
            current_project_id or fallback_project_id
        )
        project_items = [
            _serialize_project(project)
            for project in _memory_projects.values()
            if str(project.get("organization_id") or "")
            == str((organization or {}).get("id") or "")
        ]
        return {
            "current_user": user or None,
            "current_team": (
                {
                    "organization_id": str(organization.get("id") or ""),
                    "organization_name": str(organization.get("name") or ""),
                    "organization_slug": str(organization.get("slug") or ""),
                    "membership_role": str(membership.get("role") or "member"),
                }
                if organization and membership and not is_personal
                else None
            ),
            "current_project": (
                _serialize_project(current_project)
                if membership and current_project is not None
                else None
            ),
            "projects": [item for item in project_items if item is not None],
        }

    def update_current_project(self, *, user_id: str, name: str) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("Project name is required")

        self.ensure_project_state(user_id=user_id)
        membership = next(
            (item for item in _memory_memberships if item.get("user_id") == user_id),
            None,
        )
        project = _memory_projects.get(
            str((membership or {}).get("active_project_id") or DEFAULT_PROJECT_ID)
        )
        if project is None:
            raise ValueError("Project does not exist")
        project["name"] = normalized_name
        return self.get_account_team_state(user_id=user_id)

    def list_projects(self, *, user_id: str) -> dict[str, Any]:
        account_state = self.get_account_team_state(user_id=user_id)
        return {
            "items": list(account_state.get("projects") or []),
            "current_project": account_state.get("current_project"),
        }

    def create_project(self, *, user_id: str, name: str) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("Project name is required")

        membership = next(
            (item for item in _memory_memberships if item.get("user_id") == user_id),
            None,
        )
        if membership is None:
            raise ValueError("Membership does not exist")

        slug_base = _slugify_project_name(normalized_name)
        slug = slug_base
        suffix = 2
        existing_slugs = {
            str(project.get("slug") or "") for project in _memory_projects.values()
        }
        while slug in existing_slugs:
            slug = f"{slug_base}-{suffix}"
            suffix += 1

        project_id = f"project-{uuid4().hex[:12]}"
        _memory_projects[project_id] = {
            "id": project_id,
            "organization_id": membership["organization_id"],
            "name": normalized_name,
            "slug": slug,
            "status": "active",
        }
        membership["active_project_id"] = project_id
        return self.list_projects(user_id=user_id)

    def select_current_project(
        self, *, user_id: str, project_id: str
    ) -> dict[str, Any]:
        membership = next(
            (item for item in _memory_memberships if item.get("user_id") == user_id),
            None,
        )
        if membership is None:
            raise ValueError("Membership does not exist")

        project = _memory_projects.get(project_id)
        if project is None:
            raise ValueError("Project does not exist")
        if str(project.get("organization_id") or "") != str(
            membership.get("organization_id") or ""
        ):
            raise ValueError("Project does not belong to current organization")

        membership["active_project_id"] = project_id
        return self.list_projects(user_id=user_id)

    def create_job(
        self,
        *,
        task_type: str,
        summary: str,
        status: str,
        payload: dict[str, Any],
        owner_id: str | None = None,
        project_id: str | None = None,
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
            "project_id": project_id,
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
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if include_all or owner_id is None:
            jobs = list(_memory_jobs)
        else:
            jobs = [job for job in _memory_jobs if job.get("owner_id") == owner_id]
        if project_id:
            jobs = [
                job for job in jobs if str(job.get("project_id") or "") == project_id
            ]
        return [_build_job_list_item(_normalize_job_record(job)) for job in jobs]

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
                return _normalize_job_record(job)
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
            return _normalize_job_record(updated)
        return None

    def count_pending_jobs(
        self,
        *,
        owner_id: str | None = None,
        include_all: bool = False,
        project_id: str | None = None,
    ) -> int:
        return sum(
            1
            for job in self.list_jobs(
                owner_id=owner_id,
                include_all=include_all,
                project_id=project_id,
            )
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

    def __init__(self, session_factory: Callable[[], Any]):
        self._session_factory = session_factory

    @contextmanager
    def _session(self):
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def _ensure_system_user(self, session: Any) -> None:
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
                "name": row.name,
                "mode": row.mode,
                "issuer": row.issuer,
                "subject": row.subject,
                "email_verified": row.email_verified,
                "last_login_at": row.last_login_at.isoformat()
                if row.last_login_at
                else None,
            }

    def ensure_team_state(
        self,
        *,
        user_id: str,
        is_admin: bool,
    ) -> dict[str, Any]:
        with self._session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise ValueError("User does not exist")
            user.mode = "team"

            organization = session.execute(
                select(Organization).where(
                    Organization.slug == DEFAULT_TEAM_ORGANIZATION_SLUG
                )
            ).scalar_one_or_none()
            if organization is None:
                organization = Organization(
                    id=DEFAULT_TEAM_ORGANIZATION_ID,
                    name=DEFAULT_TEAM_ORGANIZATION_NAME,
                    slug=DEFAULT_TEAM_ORGANIZATION_SLUG,
                )
                session.add(organization)
                session.flush()

            membership = session.execute(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.organization_id == organization.id,
                )
            ).scalar_one_or_none()
            if membership is None:
                membership = Membership(
                    id=f"membership_{user_id}_{organization.id}",
                    user_id=user_id,
                    organization_id=organization.id,
                    active_project_id=None,
                    role="admin" if is_admin else "member",
                )
            else:
                membership.role = "admin" if is_admin else "member"
            session.add(user)
            session.add(membership)
            session.commit()

        self.ensure_project_state(user_id=user_id)
        return self.get_account_team_state(user_id=user_id)

    def ensure_personal_state(self, *, user_id: str) -> dict[str, Any]:
        with self._session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise ValueError("User does not exist")
            user.mode = "personal"

            organization_id = _build_personal_organization_id(user_id)
            organization = session.get(Organization, organization_id)
            if organization is None:
                organization = Organization(
                    id=organization_id,
                    name=PERSONAL_WORKSPACE_NAME,
                    slug=_build_personal_organization_slug(user_id),
                )
                session.add(organization)
                session.flush()

            membership = session.execute(
                select(Membership).where(
                    Membership.user_id == user_id,
                    Membership.organization_id == organization.id,
                )
            ).scalar_one_or_none()
            if membership is None:
                membership = Membership(
                    id=f"membership_{user_id}_{organization.id}",
                    user_id=user_id,
                    organization_id=organization.id,
                    active_project_id=None,
                    role="personal",
                )
            else:
                membership.role = "personal"
            session.add(user)
            session.add(membership)
            session.commit()

        self.ensure_project_state(user_id=user_id)
        return self.get_account_team_state(user_id=user_id)

    def _select_membership(self, session: Any, *, user_id: str):
        user = session.get(User, user_id)
        memberships = (
            session.execute(select(Membership).where(Membership.user_id == user_id))
            .scalars()
            .all()
        )
        if not memberships:
            return None
        return next(
            (
                item
                for item in memberships
                if (
                    str(item.role or "") == "personal"
                    if str((user.mode if user is not None else "") or "") == "personal"
                    else str(item.role or "") != "personal"
                )
            ),
            memberships[0],
        )

    def ensure_project_state(self, *, user_id: str) -> dict[str, Any]:
        with self._session() as session:
            membership = self._select_membership(session, user_id=user_id)
            if membership is None:
                raise ValueError("Membership does not exist")

            is_personal = str(membership.role or "") == "personal"
            project_slug = (
                _build_personal_project_slug(user_id)
                if is_personal
                else DEFAULT_PROJECT_SLUG
            )
            project_id = (
                _build_personal_project_id(user_id)
                if is_personal
                else DEFAULT_PROJECT_ID
            )
            project_name = (
                PERSONAL_WORKSPACE_NAME if is_personal else DEFAULT_PROJECT_NAME
            )

            project = session.execute(
                select(Project).where(
                    Project.slug == project_slug,
                    Project.organization_id == membership.organization_id,
                )
            ).scalar_one_or_none()
            if project is None:
                project = Project(
                    id=project_id,
                    organization_id=membership.organization_id,
                    name=project_name,
                    slug=project_slug,
                    status="active",
                )
                session.add(project)
                session.flush()
            if not membership.active_project_id:
                membership.active_project_id = project.id
                session.add(membership)
            session.commit()

        return self.get_account_team_state(user_id=user_id)

    def get_account_team_state(self, *, user_id: str) -> dict[str, Any]:
        with self._session() as session:
            user = session.get(User, user_id)
            membership = self._select_membership(session, user_id=user_id)
            organization = (
                session.get(Organization, membership.organization_id)
                if membership is not None
                else None
            )
            is_personal = (
                str((membership.role if membership is not None else "") or "")
                == "personal"
            )
            fallback_project_id = (
                _build_personal_project_id(user_id)
                if is_personal
                else DEFAULT_PROJECT_ID
            )
            project = (
                session.execute(
                    select(Project).where(
                        Project.organization_id == organization.id,
                        Project.id
                        == (membership.active_project_id or fallback_project_id),
                    )
                ).scalar_one_or_none()
                if organization is not None
                else None
            )
            projects = (
                session.execute(
                    select(Project).where(Project.organization_id == organization.id)
                )
                .scalars()
                .all()
                if organization is not None
                else []
            )
            return {
                "current_user": (
                    {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "mode": user.mode,
                        "issuer": user.issuer,
                        "subject": user.subject,
                        "email_verified": user.email_verified,
                        "last_login_at": user.last_login_at.isoformat()
                        if user.last_login_at
                        else None,
                    }
                    if user is not None
                    else None
                ),
                "current_team": (
                    {
                        "organization_id": organization.id,
                        "organization_name": organization.name,
                        "organization_slug": organization.slug,
                        "membership_role": membership.role,
                    }
                    if membership is not None
                    and organization is not None
                    and not is_personal
                    else None
                ),
                "current_project": (
                    _serialize_project(
                        {
                            "id": project.id,
                            "name": project.name,
                            "slug": project.slug,
                            "status": project.status,
                        }
                    )
                    if project is not None
                    else None
                ),
                "projects": [
                    _serialize_project(
                        {
                            "id": item.id,
                            "name": item.name,
                            "slug": item.slug,
                            "status": item.status,
                        }
                    )
                    for item in projects
                ],
            }

    def update_current_project(self, *, user_id: str, name: str) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("Project name is required")

        self.ensure_project_state(user_id=user_id)
        with self._session() as session:
            membership = self._select_membership(session, user_id=user_id)
            if membership is None:
                raise ValueError("Membership does not exist")

            project = session.execute(
                select(Project).where(
                    Project.organization_id == membership.organization_id,
                    Project.id == (membership.active_project_id or DEFAULT_PROJECT_ID),
                )
            ).scalar_one_or_none()
            if project is None:
                raise ValueError("Project does not exist")

            project.name = normalized_name
            session.add(project)
            session.commit()

        return self.get_account_team_state(user_id=user_id)

    def list_projects(self, *, user_id: str) -> dict[str, Any]:
        account_state = self.get_account_team_state(user_id=user_id)
        return {
            "items": list(account_state.get("projects") or []),
            "current_project": account_state.get("current_project"),
        }

    def create_project(self, *, user_id: str, name: str) -> dict[str, Any]:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("Project name is required")

        with self._session() as session:
            membership = self._select_membership(session, user_id=user_id)
            if membership is None:
                raise ValueError("Membership does not exist")

            slug_base = _slugify_project_name(normalized_name)
            slug = slug_base
            suffix = 2
            while (
                session.execute(
                    select(Project).where(Project.slug == slug)
                ).scalar_one_or_none()
                is not None
            ):
                slug = f"{slug_base}-{suffix}"
                suffix += 1

            project = Project(
                id=f"project_{uuid4().hex[:12]}",
                organization_id=membership.organization_id,
                name=normalized_name,
                slug=slug,
                status="active",
            )
            session.add(project)
            session.flush()
            membership.active_project_id = project.id
            session.add(membership)
            session.commit()

        return self.list_projects(user_id=user_id)

    def select_current_project(
        self, *, user_id: str, project_id: str
    ) -> dict[str, Any]:
        with self._session() as session:
            membership = self._select_membership(session, user_id=user_id)
            if membership is None:
                raise ValueError("Membership does not exist")

            project = session.get(Project, project_id)
            if project is None:
                raise ValueError("Project does not exist")
            if project.organization_id != membership.organization_id:
                raise ValueError("Project does not belong to current organization")

            membership.active_project_id = project.id
            session.add(membership)
            session.commit()

        return self.list_projects(user_id=user_id)

    def create_job(
        self,
        *,
        task_type: str,
        summary: str,
        status: str,
        payload: dict[str, Any],
        owner_id: str | None = None,
        project_id: str | None = None,
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
            resolved_project_id = str(
                project_id or payload.get("projectId") or ""
            ).strip()
            job = Job(
                id=record_id,
                type=task_type,
                status=status,
                owner_id=resolved_owner_id,
                project_id=resolved_project_id or None,
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
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            statement = select(Job)
            if not include_all and owner_id:
                statement = statement.where(Job.owner_id == owner_id)
            if project_id:
                statement = statement.where(Job.project_id == project_id)
            rows = (
                session.execute(statement.order_by(Job.created_at.desc()).limit(50))
                .scalars()
                .all()
            )
            return [_build_job_list_item(_normalize_job_record(row)) for row in rows]

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
        project_id: str | None = None,
    ) -> int:
        return sum(
            1
            for job in self.list_jobs(
                owner_id=owner_id,
                include_all=include_all,
                project_id=project_id,
            )
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

    def _with_fallback(
        self,
        operation: str,
        func: Callable[[], Any],
        *args: Any,
        **kwargs: Any,
    ):
        if self._using_fallback:
            return getattr(self._fallback, operation)(*args, **kwargs)

        try:
            return func()
        except Exception as exc:  # pragma: no cover - defensive fallback path
            self._using_fallback = True
            self._fallback_reason = str(exc)
            return getattr(self._fallback, operation)(*args, **kwargs)

    def create_job(self, **kwargs):
        return self._with_fallback(
            "create_job",
            lambda: self._primary.create_job(**kwargs),
            **kwargs,
        )

    def upsert_user(self, **kwargs):
        return self._with_fallback(
            "upsert_user",
            lambda: self._primary.upsert_user(**kwargs),
            **kwargs,
        )

    def ensure_team_state(self, **kwargs):
        return self._with_fallback(
            "ensure_team_state",
            lambda: self._primary.ensure_team_state(**kwargs),
            **kwargs,
        )

    def ensure_personal_state(self, **kwargs):
        return self._with_fallback(
            "ensure_personal_state",
            lambda: self._primary.ensure_personal_state(**kwargs),
            **kwargs,
        )

    def ensure_project_state(self, **kwargs):
        return self._with_fallback(
            "ensure_project_state",
            lambda: self._primary.ensure_project_state(**kwargs),
            **kwargs,
        )

    def get_account_team_state(self, **kwargs):
        return self._with_fallback(
            "get_account_team_state",
            lambda: self._primary.get_account_team_state(**kwargs),
            **kwargs,
        )

    def update_current_project(self, **kwargs):
        return self._with_fallback(
            "update_current_project",
            lambda: self._primary.update_current_project(**kwargs),
            **kwargs,
        )

    def list_projects(self, **kwargs):
        return self._with_fallback(
            "list_projects",
            lambda: self._primary.list_projects(**kwargs),
            **kwargs,
        )

    def create_project(self, **kwargs):
        return self._with_fallback(
            "create_project",
            lambda: self._primary.create_project(**kwargs),
            **kwargs,
        )

    def select_current_project(self, **kwargs):
        return self._with_fallback(
            "select_current_project",
            lambda: self._primary.select_current_project(**kwargs),
            **kwargs,
        )

    def list_jobs(self, **kwargs):
        return self._with_fallback(
            "list_jobs",
            lambda: self._primary.list_jobs(**kwargs),
            **kwargs,
        )

    def count_pending_jobs(self, **kwargs):
        return self._with_fallback(
            "count_pending_jobs",
            lambda: self._primary.count_pending_jobs(**kwargs),
            **kwargs,
        )

    def get_job(self, job_id: str, **kwargs):
        return self._with_fallback(
            "get_job",
            lambda: self._primary.get_job(job_id, **kwargs),
            job_id,
            **kwargs,
        )

    def update_job(self, job_id: str, **kwargs):
        return self._with_fallback(
            "update_job",
            lambda: self._primary.update_job(job_id, **kwargs),
            job_id,
            **kwargs,
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
    database_url = normalize_database_url(os.getenv("DATABASE_URL", "").strip())
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
