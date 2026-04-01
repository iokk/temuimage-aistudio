from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pydantic import Field

from apps.api.async_dispatcher import get_async_backend_meta
from apps.api.core.auth import Principal, get_current_principal, require_admin
from apps.api.core.config import get_settings
from apps.api.core.system_config import get_system_execution_config
from apps.api.core.system_config import serialize_system_execution_config
from apps.api.core.system_config import update_system_execution_config
from apps.api.job_repository import job_repository
import os


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


router = APIRouter(prefix="/system", tags=["system"])


class SystemExecutionConfigRequest(BaseModel):
    title_model: str = Field(min_length=1, max_length=200)
    translate_provider: str = Field(min_length=1, max_length=32)
    translate_image_model: str = Field(min_length=1, max_length=200)
    translate_analysis_model: str = Field(min_length=1, max_length=200)
    quick_image_model: str = Field(min_length=1, max_length=200)
    batch_image_model: str = Field(min_length=1, max_length=200)
    relay_api_base: str = Field(default="", max_length=500)
    relay_api_key: str = Field(default="", max_length=500)
    relay_default_image_model: str = Field(default="", max_length=200)
    gemini_api_key: str = Field(default="", max_length=500)


def _build_runtime_payload(principal: Principal | None = None) -> dict:
    settings = get_settings()
    execution_config = get_system_execution_config()
    storage_meta = job_repository.get_backend_meta()
    async_meta = get_async_backend_meta()
    team_admins = _parse_csv(os.getenv("TEAM_ADMIN_EMAILS"))
    team_domains = _parse_csv(os.getenv("TEAM_ALLOWED_EMAIL_DOMAINS"))
    casdoor_enabled = bool(
        settings.casdoor_issuer
        and settings.casdoor_client_id
        and settings.casdoor_client_secret
    )
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
    if not casdoor_enabled:
        warnings.append("未配置 Casdoor，统一身份登录不可用。")

    auth_provider = "Casdoor" if casdoor_enabled else "Unconfigured"

    ready_for_distributed_workers = bool(
        settings.database_url
        and settings.redis_url
        and storage_meta.get("persistence_ready")
        and async_meta.get("execution_storage_compatible")
        and async_meta.get("execution_queue_ready")
    )
    account_state = (
        job_repository.get_account_team_state(user_id=principal.user_id)
        if principal is not None
        else {"current_user": None, "current_team": None, "current_project": None}
    )
    current_user = dict(account_state.get("current_user") or {})
    if current_user and principal is not None:
        current_user["is_admin"] = principal.is_admin
        current_user["is_team_member"] = principal.is_team_member

    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "database_configured": bool(settings.database_url),
        "redis_configured": bool(settings.redis_url),
        "auth_provider": auth_provider,
        "team_admin_count": len(team_admins),
        "team_allowed_domain_count": len(team_domains),
        "default_title_model": execution_config.title_model,
        "default_translate_provider": execution_config.translate_provider,
        "default_translate_image_model": execution_config.translate_image_model,
        "default_translate_analysis_model": execution_config.translate_analysis_model,
        "default_quick_image_model": execution_config.quick_image_model,
        "default_batch_image_model": execution_config.batch_image_model,
        "relay_api_base_configured": bool(execution_config.relay_api_base),
        "relay_api_key_configured": bool(execution_config.relay_api_key),
        "gemini_api_key_configured": bool(execution_config.gemini_api_key),
        "system_config_source": execution_config.source,
        "system_config_persistence_enabled": execution_config.persistence_enabled,
        "warnings": warnings,
        "ready_for_distributed_workers": ready_for_distributed_workers,
        "current_user": current_user or None,
        "current_team": account_state.get("current_team"),
        "current_project": account_state.get("current_project"),
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
def system_runtime(principal: Principal = Depends(get_current_principal)):
    return _build_runtime_payload(principal)


@router.get("/config")
def system_config(_principal: Principal = Depends(require_admin)):
    return serialize_system_execution_config(get_system_execution_config())


@router.put("/config")
def system_config_update(
    payload: SystemExecutionConfigRequest,
    _principal: Principal = Depends(require_admin),
):
    config = update_system_execution_config(payload.model_dump())
    return serialize_system_execution_config(config)


@router.get("/readiness")
def system_readiness(_principal: Principal = Depends(require_admin)):
    runtime = _build_runtime_payload()
    return {
        "status": "ready" if runtime["ready_for_distributed_workers"] else "degraded",
        "blocking_warnings": runtime["warnings"],
        "ready_for_distributed_workers": runtime["ready_for_distributed_workers"],
    }
