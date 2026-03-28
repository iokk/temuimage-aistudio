from __future__ import annotations

from fastapi import APIRouter

from apps.api.async_dispatcher import get_async_backend_meta
from apps.api.core.config import get_settings
from apps.api.job_repository import job_repository
from apps.api.routers.batch import DEFAULT_IMAGE_MODEL as BATCH_IMAGE_MODEL
from apps.api.routers.quick import DEFAULT_IMAGE_MODEL as QUICK_IMAGE_MODEL
from apps.api.routers.title import DEFAULT_MODEL as TITLE_MODEL
from apps.api.routers.translate import DEFAULT_ANALYSIS_MODEL
from apps.api.routers.translate import DEFAULT_IMAGE_MODEL
import os


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


router = APIRouter(prefix="/system", tags=["system"])


def _build_runtime_payload() -> dict:
    settings = get_settings()
    storage_meta = job_repository.get_backend_meta()
    async_meta = get_async_backend_meta()
    team_admins = _parse_csv(os.getenv("TEAM_ADMIN_EMAILS"))
    bootstrap_login_email = os.getenv("BOOTSTRAP_LOGIN_EMAIL", "").strip()
    if bootstrap_login_email and bootstrap_login_email not in team_admins:
        team_admins.append(bootstrap_login_email)
    team_domains = _parse_csv(os.getenv("TEAM_ALLOWED_EMAIL_DOMAINS"))
    casdoor_enabled = bool(
        os.getenv("CASDOOR_ISSUER")
        and os.getenv("CASDOOR_CLIENT_ID")
        and os.getenv("CASDOOR_CLIENT_SECRET")
    )
    bootstrap_enabled = bool(bootstrap_login_email)
    warnings: list[str] = []

    if not settings.database_url:
        warnings.append("未配置 DATABASE_URL，无法进入持久化任务模式。")
    if not settings.redis_url:
        warnings.append("未配置 REDIS_URL，Celery 队列后端不可用。")
    if not storage_meta.get("persistence_ready"):
        warnings.append("任务存储仍在原型模式，跨进程任务状态不会持久化。")
    if not async_meta.get("execution_storage_compatible"):
        warnings.append("当前执行后端与任务存储不兼容，系统会自动回退到 inline。")
    if not team_admins:
        warnings.append("未配置 TEAM_ADMIN_EMAILS，团队管理员入口仍不稳定。")
    if not casdoor_enabled and not bootstrap_enabled:
        warnings.append("未配置可用登录方式，至少需要 Casdoor 或内置引导账号。")

    if casdoor_enabled and bootstrap_enabled:
        auth_provider = "Casdoor + Bootstrap"
    elif casdoor_enabled:
        auth_provider = "Casdoor"
    elif bootstrap_enabled:
        auth_provider = "Bootstrap"
    else:
        auth_provider = "Unconfigured"

    ready_for_distributed_workers = bool(
        settings.database_url
        and settings.redis_url
        and storage_meta.get("persistence_ready")
        and async_meta.get("execution_storage_compatible")
    )

    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "database_configured": bool(settings.database_url),
        "redis_configured": bool(settings.redis_url),
        "auth_provider": auth_provider,
        "team_admin_count": len(team_admins),
        "team_allowed_domain_count": len(team_domains),
        "default_title_model": TITLE_MODEL,
        "default_translate_image_model": DEFAULT_IMAGE_MODEL,
        "default_translate_analysis_model": DEFAULT_ANALYSIS_MODEL,
        "default_quick_image_model": QUICK_IMAGE_MODEL,
        "default_batch_image_model": BATCH_IMAGE_MODEL,
        "warnings": warnings,
        "ready_for_distributed_workers": ready_for_distributed_workers,
        **storage_meta,
        **async_meta,
    }


@router.get("/health")
def system_health():
    settings = get_settings()
    return {
        "service": "api",
        "status": "ok",
        "version": settings.app_version,
    }


@router.get("/runtime")
def system_runtime():
    return _build_runtime_payload()


@router.get("/readiness")
def system_readiness():
    runtime = _build_runtime_payload()
    return {
        "status": "ready" if runtime["ready_for_distributed_workers"] else "degraded",
        "blocking_warnings": runtime["warnings"],
        "ready_for_distributed_workers": runtime["ready_for_distributed_workers"],
    }
