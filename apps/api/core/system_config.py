from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from functools import lru_cache
import os
from threading import Lock
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from apps.api.core.config import get_settings
from apps.api.db.models import SystemConfig


SYSTEM_EXECUTION_CONFIG_KEY = "system_execution"

_memory_lock = Lock()
_memory_override: dict[str, Any] = {}


@dataclass(frozen=True)
class SystemExecutionConfig:
    title_model: str
    translate_provider: str
    translate_image_model: str
    translate_analysis_model: str
    quick_image_model: str
    batch_image_model: str
    relay_api_base: str
    relay_api_key: str
    relay_default_image_model: str
    gemini_api_key: str
    source: str
    persistence_enabled: bool


DEFAULT_EXECUTION_CONFIG = {
    "title_model": "gemini-3.1-pro",
    "translate_provider": "gemini",
    "translate_image_model": "gemini-3.1-flash-image-preview",
    "translate_analysis_model": "gemini-3.1-pro",
    "quick_image_model": "gemini-3.1-flash-image-preview",
    "batch_image_model": "gemini-3.1-flash-image-preview",
    "relay_api_base": "",
    "relay_api_key": "",
    "relay_default_image_model": "gemini-3.1-flash-image-preview",
    "gemini_api_key": "",
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _build_env_defaults() -> dict[str, str]:
    return {
        "title_model": _clean_text(
            os.getenv("TITLE_TEXT_MODEL", DEFAULT_EXECUTION_CONFIG["title_model"])
        )
        or DEFAULT_EXECUTION_CONFIG["title_model"],
        "translate_provider": _clean_text(
            os.getenv(
                "TRANSLATE_PROVIDER", DEFAULT_EXECUTION_CONFIG["translate_provider"]
            )
        )
        or DEFAULT_EXECUTION_CONFIG["translate_provider"],
        "translate_image_model": _clean_text(
            os.getenv(
                "TRANSLATE_IMAGE_MODEL",
                DEFAULT_EXECUTION_CONFIG["translate_image_model"],
            )
        )
        or DEFAULT_EXECUTION_CONFIG["translate_image_model"],
        "translate_analysis_model": _clean_text(
            os.getenv(
                "TRANSLATE_ANALYSIS_MODEL",
                DEFAULT_EXECUTION_CONFIG["translate_analysis_model"],
            )
        )
        or DEFAULT_EXECUTION_CONFIG["translate_analysis_model"],
        "quick_image_model": _clean_text(
            os.getenv(
                "QUICK_IMAGE_MODEL", DEFAULT_EXECUTION_CONFIG["quick_image_model"]
            )
        )
        or DEFAULT_EXECUTION_CONFIG["quick_image_model"],
        "batch_image_model": _clean_text(
            os.getenv(
                "BATCH_IMAGE_MODEL", DEFAULT_EXECUTION_CONFIG["batch_image_model"]
            )
        )
        or DEFAULT_EXECUTION_CONFIG["batch_image_model"],
        "relay_api_base": _clean_text(os.getenv("RELAY_API_BASE")),
        "relay_api_key": _clean_text(os.getenv("RELAY_API_KEY")),
        "relay_default_image_model": _clean_text(
            os.getenv(
                "RELAY_DEFAULT_IMAGE_MODEL",
                DEFAULT_EXECUTION_CONFIG["relay_default_image_model"],
            )
        )
        or DEFAULT_EXECUTION_CONFIG["relay_default_image_model"],
        "gemini_api_key": _clean_text(os.getenv("GEMINI_API_KEY")),
    }


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session] | None:
    settings = get_settings()
    if not settings.database_url:
        return None

    try:
        engine = create_engine(settings.database_url, future=True)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)
    except (ModuleNotFoundError, SQLAlchemyError, ValueError):
        return None


def _load_database_override() -> dict[str, Any] | None:
    session_factory = _session_factory()
    if session_factory is None:
        return None

    try:
        with session_factory() as session:
            row = session.execute(
                select(SystemConfig).where(
                    SystemConfig.config_key == SYSTEM_EXECUTION_CONFIG_KEY
                )
            ).scalar_one_or_none()
            if row is None or not isinstance(row.config_value, dict):
                return None
            return row.config_value
    except SQLAlchemyError:
        return None


def _save_database_override(payload: dict[str, Any]) -> bool:
    session_factory = _session_factory()
    if session_factory is None:
        return False

    try:
        with session_factory() as session:
            row = session.execute(
                select(SystemConfig).where(
                    SystemConfig.config_key == SYSTEM_EXECUTION_CONFIG_KEY
                )
            ).scalar_one_or_none()
            if row is None:
                row = SystemConfig(
                    id=SYSTEM_EXECUTION_CONFIG_KEY,
                    config_key=SYSTEM_EXECUTION_CONFIG_KEY,
                    config_value=payload,
                )
                session.add(row)
            else:
                row.config_value = payload
            session.commit()
        return True
    except SQLAlchemyError:
        return False


def _normalize_override(payload: dict[str, Any] | None) -> dict[str, str]:
    value = payload if isinstance(payload, dict) else {}
    return {
        key: _clean_text(value.get(key, DEFAULT_EXECUTION_CONFIG[key]))
        for key in DEFAULT_EXECUTION_CONFIG
    }


def get_system_execution_config() -> SystemExecutionConfig:
    env_defaults = _build_env_defaults()
    database_override = _load_database_override()
    if database_override is not None:
        merged = {**env_defaults, **_normalize_override(database_override)}
        return SystemExecutionConfig(
            **merged,
            source="database",
            persistence_enabled=True,
        )

    with _memory_lock:
        memory_override = dict(_memory_override)

    if memory_override:
        merged = {**env_defaults, **_normalize_override(memory_override)}
        return SystemExecutionConfig(
            **merged,
            source="memory",
            persistence_enabled=False,
        )

    return SystemExecutionConfig(
        **env_defaults,
        source="environment",
        persistence_enabled=_session_factory() is not None,
    )


def update_system_execution_config(payload: dict[str, Any]) -> SystemExecutionConfig:
    normalized = _build_updated_config_payload(payload)
    saved = _save_database_override(normalized)
    if saved:
        return get_system_execution_config()

    with _memory_lock:
        _memory_override.clear()
        _memory_override.update(normalized)

    return get_system_execution_config()


def serialize_system_execution_config(config: SystemExecutionConfig) -> dict[str, Any]:
    payload = asdict(config)
    payload["relay_api_key_preview"] = _mask_secret(config.relay_api_key)
    payload["gemini_api_key_preview"] = _mask_secret(config.gemini_api_key)
    payload.pop("relay_api_key", None)
    payload.pop("gemini_api_key", None)
    return payload


def _build_updated_config_payload(payload: dict[str, Any]) -> dict[str, str]:
    current = get_system_execution_config()
    merged = {
        **_normalize_override(asdict(current)),
        **_normalize_override(payload),
    }

    for secret_key in ("relay_api_key", "gemini_api_key"):
        incoming_value = _clean_text((payload or {}).get(secret_key))
        if not incoming_value:
            merged[secret_key] = _clean_text(getattr(current, secret_key, ""))

    return merged


def _mask_secret(value: str) -> str:
    secret = _clean_text(value)
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}***{secret[-4:]}"
