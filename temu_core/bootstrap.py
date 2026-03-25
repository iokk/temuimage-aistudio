from __future__ import annotations

from pathlib import Path
import threading

from alembic import command
from alembic.config import Config

from .billing import seed_default_workspace
from .db import session_scope
from .settings import database_enabled, get_platform_settings


_BOOTSTRAP_LOCK = threading.Lock()
_BOOTSTRAP_STATE = {
    "attempted": False,
    "database_enabled": False,
    "migrated": False,
    "seeded": False,
    "error": "",
}


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config


def run_platform_migrations() -> None:
    command.upgrade(_alembic_config(), "head")


def bootstrap_platform_runtime() -> dict:
    settings = get_platform_settings()
    with _BOOTSTRAP_LOCK:
        if _BOOTSTRAP_STATE["attempted"]:
            return dict(_BOOTSTRAP_STATE)
        _BOOTSTRAP_STATE["attempted"] = True
        _BOOTSTRAP_STATE["database_enabled"] = database_enabled()
        if not _BOOTSTRAP_STATE["database_enabled"]:
            return dict(_BOOTSTRAP_STATE)
        try:
            if settings.platform_auto_migrate:
                run_platform_migrations()
                _BOOTSTRAP_STATE["migrated"] = True
            if settings.platform_seed_defaults:
                with session_scope() as session:
                    seed_default_workspace(session)
                _BOOTSTRAP_STATE["seeded"] = True
        except Exception as exc:
            _BOOTSTRAP_STATE["error"] = str(exc)
        return dict(_BOOTSTRAP_STATE)


def get_platform_bootstrap_state() -> dict:
    return dict(_BOOTSTRAP_STATE)
