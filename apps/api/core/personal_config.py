from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from apps.api.core.config import get_settings
from apps.api.core.system_config import SystemExecutionConfig
from apps.api.core.system_config import get_system_execution_config
from apps.api.db.models import SystemConfig
from temu_core.credential_resolver import resolve_runtime_credentials


PERSONAL_CONFIG_KEY_PREFIX = "personal_execution:"

_memory_lock = Lock()
_memory_override: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class PersonalExecutionConfig:
    use_personal_credentials: bool
    provider: str
    relay_api_base: str
    relay_api_key: str
    relay_default_image_model: str
    gemini_api_key: str
    source: str
    persistence_enabled: bool


DEFAULT_PERSONAL_CONFIG = {
    "use_personal_credentials": False,
    "provider": "gemini",
    "relay_api_base": "",
    "relay_api_key": "",
    "relay_default_image_model": "gemini-3.1-flash-image-preview",
    "gemini_api_key": "",
}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _build_config_key(user_id: str) -> str:
    return f"{PERSONAL_CONFIG_KEY_PREFIX}{str(user_id).strip()}"


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


def _load_database_override(user_id: str) -> dict[str, Any] | None:
    session_factory = _session_factory()
    if session_factory is None:
        return None

    try:
        with session_factory() as session:
            row = session.execute(
                select(SystemConfig).where(
                    SystemConfig.config_key == _build_config_key(user_id)
                )
            ).scalar_one_or_none()
            if row is None or not isinstance(row.config_value, dict):
                return None
            return row.config_value
    except SQLAlchemyError:
        return None


def _save_database_override(user_id: str, payload: dict[str, Any]) -> bool:
    session_factory = _session_factory()
    if session_factory is None:
        return False

    config_key = _build_config_key(user_id)
    try:
        with session_factory() as session:
            row = session.execute(
                select(SystemConfig).where(SystemConfig.config_key == config_key)
            ).scalar_one_or_none()
            if row is None:
                row = SystemConfig(
                    id=config_key,
                    config_key=config_key,
                    config_value=payload,
                )
                session.add(row)
            else:
                row.config_value = payload
            session.commit()
        return True
    except SQLAlchemyError:
        return False


def _normalize_override(payload: dict[str, Any] | None) -> dict[str, Any]:
    value = payload if isinstance(payload, dict) else {}
    return {
        "use_personal_credentials": _clean_bool(
            value.get(
                "use_personal_credentials",
                DEFAULT_PERSONAL_CONFIG["use_personal_credentials"],
            )
        ),
        "provider": _clean_text(
            value.get("provider", DEFAULT_PERSONAL_CONFIG["provider"])
        )
        or DEFAULT_PERSONAL_CONFIG["provider"],
        "relay_api_base": _clean_text(
            value.get("relay_api_base", DEFAULT_PERSONAL_CONFIG["relay_api_base"])
        ),
        "relay_api_key": _clean_text(
            value.get("relay_api_key", DEFAULT_PERSONAL_CONFIG["relay_api_key"])
        ),
        "relay_default_image_model": _clean_text(
            value.get(
                "relay_default_image_model",
                DEFAULT_PERSONAL_CONFIG["relay_default_image_model"],
            )
        )
        or DEFAULT_PERSONAL_CONFIG["relay_default_image_model"],
        "gemini_api_key": _clean_text(
            value.get("gemini_api_key", DEFAULT_PERSONAL_CONFIG["gemini_api_key"])
        ),
    }


def get_personal_execution_config(user_id: str) -> PersonalExecutionConfig:
    database_override = _load_database_override(user_id)
    if database_override is not None:
        return PersonalExecutionConfig(
            **_normalize_override(database_override),
            source="database",
            persistence_enabled=True,
        )

    with _memory_lock:
        memory_override = dict(_memory_override.get(user_id) or {})

    if memory_override:
        return PersonalExecutionConfig(
            **_normalize_override(memory_override),
            source="memory",
            persistence_enabled=False,
        )

    return PersonalExecutionConfig(
        **DEFAULT_PERSONAL_CONFIG,
        source="environment",
        persistence_enabled=_session_factory() is not None,
    )


def _build_updated_config_payload(
    user_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = get_personal_execution_config(user_id)
    merged = {
        **_normalize_override(asdict(current)),
        **_normalize_override(payload),
    }

    for secret_key in ("relay_api_key", "gemini_api_key"):
        incoming_value = _clean_text((payload or {}).get(secret_key))
        if not incoming_value:
            merged[secret_key] = _clean_text(getattr(current, secret_key, ""))

    return merged


def update_personal_execution_config(
    user_id: str, payload: dict[str, Any]
) -> PersonalExecutionConfig:
    normalized = _build_updated_config_payload(user_id, payload)
    saved = _save_database_override(user_id, normalized)
    if saved:
        return get_personal_execution_config(user_id)

    with _memory_lock:
        _memory_override[user_id] = normalized

    return get_personal_execution_config(user_id)


def _mask_secret(value: str) -> str:
    secret = _clean_text(value)
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}***{secret[-4:]}"


def serialize_personal_execution_config(
    config: PersonalExecutionConfig,
) -> dict[str, Any]:
    payload = asdict(config)
    payload["relay_api_key_preview"] = _mask_secret(config.relay_api_key)
    payload["gemini_api_key_preview"] = _mask_secret(config.gemini_api_key)
    payload.pop("relay_api_key", None)
    payload.pop("gemini_api_key", None)
    return payload


def get_effective_execution_config_for_user(
    user_id: str | None,
) -> SystemExecutionConfig | PersonalExecutionConfig:
    system_config = get_system_execution_config()
    if not user_id:
        return system_config

    personal_config = get_personal_execution_config(user_id)
    if not personal_config.use_personal_credentials:
        return system_config

    resolved = resolve_runtime_credentials(
        preferred_provider=system_config.translate_provider,
        use_own_credentials=True,
        own_provider=personal_config.provider,
        own_gemini_key=personal_config.gemini_api_key,
        own_relay_key=personal_config.relay_api_key,
        own_relay_base=personal_config.relay_api_base,
        own_relay_model=personal_config.relay_default_image_model,
        system_gemini_key=system_config.gemini_api_key,
        system_relay_key=system_config.relay_api_key,
        system_relay_base=system_config.relay_api_base,
        system_relay_model=system_config.relay_default_image_model,
    )

    provider = str(resolved.get("provider") or "").strip().lower()
    if provider == "relay":
        if not (
            str(resolved.get("api_key") or "").strip()
            and str(resolved.get("base_url") or "").strip()
        ):
            return system_config
        return SystemExecutionConfig(
            title_model=system_config.title_model,
            translate_provider="relay",
            translate_image_model=system_config.translate_image_model,
            translate_analysis_model=system_config.translate_analysis_model,
            quick_image_model=system_config.quick_image_model,
            batch_image_model=system_config.batch_image_model,
            relay_api_base=str(resolved.get("base_url") or "").strip(),
            relay_api_key=str(resolved.get("api_key") or "").strip(),
            relay_default_image_model=str(resolved.get("model") or "").strip()
            or system_config.relay_default_image_model,
            gemini_api_key="",
            source=f"personal:{personal_config.source}",
            persistence_enabled=personal_config.persistence_enabled,
        )

    if not str(resolved.get("api_key") or "").strip():
        return system_config
    return SystemExecutionConfig(
        title_model=system_config.title_model,
        translate_provider="gemini",
        translate_image_model=system_config.translate_image_model,
        translate_analysis_model=system_config.translate_analysis_model,
        quick_image_model=system_config.quick_image_model,
        batch_image_model=system_config.batch_image_model,
        relay_api_base="",
        relay_api_key="",
        relay_default_image_model=system_config.relay_default_image_model,
        gemini_api_key=str(resolved.get("api_key") or "").strip(),
        source=f"personal:{personal_config.source}",
        persistence_enabled=personal_config.persistence_enabled,
    )
