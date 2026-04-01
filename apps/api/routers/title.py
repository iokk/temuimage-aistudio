from __future__ import annotations

import re

from fastapi import APIRouter, Depends

from apps.api.core.auth import Principal, get_current_principal
from apps.api.core.personal_config import get_effective_execution_config_for_user
from apps.api.job_repository import job_repository
from apps.api.task_execution import DEFAULT_TITLE_TEMPLATE_KEY
from apps.api.task_execution import IMAGE_TITLE_TEMPLATE_KEY
from apps.api.task_execution import list_title_template_options
from apps.api.task_execution import _resolve_title_provider


router = APIRouter(prefix="/title", tags=["title"])


def _build_title_blocking_reason(config) -> str:
    try:
        _resolve_title_provider(config)
        return ""
    except ValueError as exc:
        return str(exc)


@router.get("/context")
def title_context(principal: Principal = Depends(get_current_principal)):
    config = get_effective_execution_config_for_user(principal.user_id)
    account_state = job_repository.get_account_team_state(user_id=principal.user_id)
    blocking_reason = _build_title_blocking_reason(config)
    provider = ""
    if not blocking_reason:
        provider = _resolve_title_provider(config)

    warnings: list[str] = []
    if not principal.is_team_member:
        warnings.append("当前为个人模式，标题任务会优先使用你的个人执行配置。")
    if str(config.source or "").startswith("personal:"):
        warnings.append("当前标题任务将使用个人凭据执行。")
    if provider == "relay" and not re.match(
        r"^gemini", str(config.title_model or ""), re.I
    ):
        warnings.append("当前标题模型经 relay 文本能力执行，请确认模型通道稳定。")

    return {
        "ready": not blocking_reason,
        "default_model": str(config.title_model or "").strip(),
        "default_template_key": DEFAULT_TITLE_TEMPLATE_KEY,
        "image_template_key": IMAGE_TITLE_TEMPLATE_KEY,
        "template_options": list_title_template_options(),
        "provider": provider,
        "config_source": str(config.source or "").strip() or "environment",
        "warnings": warnings,
        "blocking_reason": blocking_reason or None,
        "current_project": account_state.get("current_project"),
        "current_team": account_state.get("current_team"),
    }
