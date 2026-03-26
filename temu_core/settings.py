from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _clean_env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def normalize_database_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+" not in raw.split("://", 1)[0]:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


@dataclass(frozen=True)
class PlatformSettings:
    database_url: str
    redis_url: str
    platform_auto_migrate: bool
    platform_seed_defaults: bool
    default_org_name: str
    default_project_name: str
    backup_bucket: str
    backup_prefix: str
    encryption_key: str


@lru_cache(maxsize=1)
def get_platform_settings() -> PlatformSettings:
    return PlatformSettings(
        database_url=normalize_database_url(_clean_env("DATABASE_URL")),
        redis_url=_clean_env("REDIS_URL"),
        platform_auto_migrate=_env_flag("PLATFORM_AUTO_MIGRATE", False),
        platform_seed_defaults=_env_flag("PLATFORM_SEED_DEFAULTS", True),
        default_org_name=_clean_env("PLATFORM_DEFAULT_ORG_NAME", "TEMU Team Workspace"),
        default_project_name=_clean_env(
            "PLATFORM_DEFAULT_PROJECT_NAME", "Default Project"
        ),
        backup_bucket=_clean_env("BACKUP_S3_BUCKET"),
        backup_prefix=_clean_env("BACKUP_S3_PREFIX", "temu-backups/"),
        encryption_key=_clean_env("PLATFORM_ENCRYPTION_KEY"),
    )


def database_enabled() -> bool:
    return bool(get_platform_settings().database_url)
