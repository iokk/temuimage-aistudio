from __future__ import annotations

from pathlib import Path
import importlib.util
import os
import sys
from types import ModuleType
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from apps.api.core.config import get_settings


JOB_REPOSITORY_PATH = Path("apps/api/job_repository.py")


def _load_module(
    module_name: str, file_path: Path, stub_modules: dict[str, ModuleType]
):
    for name, module in stub_modules.items():
        sys.modules[name] = module
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_job_repository_stubs() -> dict[str, ModuleType]:
    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.create_engine = lambda *args, **kwargs: object()
    sqlalchemy.select = lambda *args, **kwargs: SimpleNamespace(
        where=lambda *a, **k: None
    )

    sqlalchemy_exc = ModuleType("sqlalchemy.exc")
    sqlalchemy_exc.SQLAlchemyError = Exception

    sqlalchemy_orm = ModuleType("sqlalchemy.orm")
    sqlalchemy_orm.Session = object

    class _FakeSessionMaker:
        def __call__(self, *args, **kwargs):
            return None

    sqlalchemy_orm.sessionmaker = _FakeSessionMaker

    db_models = ModuleType("apps.api.db.models")
    db_models.Job = type("Job", (), {})
    db_models.Membership = type("Membership", (), {})
    db_models.Organization = type("Organization", (), {})
    db_models.Project = type("Project", (), {})
    db_models.User = type("User", (), {})

    settings_module = ModuleType("temu_core.settings")
    settings_module.normalize_database_url = lambda value: (
        value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://")
        else value
    )

    return {
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.exc": sqlalchemy_exc,
        "sqlalchemy.orm": sqlalchemy_orm,
        "apps.api.db.models": db_models,
        "temu_core.settings": settings_module,
    }


class ApiDatabaseUrlNormalizationTest(unittest.TestCase):
    def test_get_settings_normalizes_postgresql_scheme(self):
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:pass@db:5432/xiaobaitu"},
            clear=False,
        ):
            settings = get_settings()

        self.assertEqual(
            settings.database_url,
            "postgresql+psycopg://user:pass@db:5432/xiaobaitu",
        )

    def test_repository_uses_normalized_database_url(self):
        module = _load_module(
            "job_repository_database_url_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        with patch.dict(
            os.environ,
            {
                "JOB_STORE_BACKEND": "database",
                "DATABASE_URL": "postgresql://user:pass@db:5432/xiaobaitu",
            },
            clear=False,
        ):
            with patch.object(module, "create_engine") as create_engine:
                module.build_job_repository()

        create_engine.assert_called_once_with(
            "postgresql+psycopg://user:pass@db:5432/xiaobaitu",
            future=True,
        )


if __name__ == "__main__":
    unittest.main()
