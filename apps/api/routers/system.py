from __future__ import annotations

from fastapi import APIRouter

from apps.api.core.config import get_settings


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def system_health():
    settings = get_settings()
    return {
        "service": "api",
        "status": "ok",
        "version": settings.app_version,
    }
