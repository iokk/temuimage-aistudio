from __future__ import annotations

from pathlib import Path
import importlib.util
import os
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest


SYSTEM_CONFIG_PATH = Path("apps/api/core/system_config.py")
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


def _build_system_config_stubs() -> dict[str, ModuleType]:
    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.create_engine = lambda *args, **kwargs: object()
    sqlalchemy.select = lambda *args, **kwargs: None

    sqlalchemy_exc = ModuleType("sqlalchemy.exc")
    sqlalchemy_exc.SQLAlchemyError = Exception

    sqlalchemy_orm = ModuleType("sqlalchemy.orm")

    class _FakeSession:
        pass

    class _FakeSessionMaker:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __call__(self, *args, **kwargs):
            return None

    sqlalchemy_orm.Session = _FakeSession
    sqlalchemy_orm.sessionmaker = _FakeSessionMaker

    config_module = ModuleType("apps.api.core.config")
    config_module.get_settings = lambda: SimpleNamespace(database_url="")

    db_models = ModuleType("apps.api.db.models")

    class _FakeSystemConfig:
        config_key = "system_execution"

    db_models.SystemConfig = _FakeSystemConfig

    return {
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.exc": sqlalchemy_exc,
        "sqlalchemy.orm": sqlalchemy_orm,
        "apps.api.core.config": config_module,
        "apps.api.db.models": db_models,
    }


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

    class _FakeJob:
        pass

    class _FakeMembership:
        pass

    class _FakeOrganization:
        pass

    class _FakeProject:
        pass

    class _FakeUser:
        pass

    db_models.Job = _FakeJob
    db_models.Membership = _FakeMembership
    db_models.Organization = _FakeOrganization
    db_models.Project = _FakeProject
    db_models.User = _FakeUser

    settings_module = ModuleType("temu_core.settings")
    settings_module.normalize_database_url = lambda value: value

    return {
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.exc": sqlalchemy_exc,
        "sqlalchemy.orm": sqlalchemy_orm,
        "apps.api.db.models": db_models,
        "temu_core.settings": settings_module,
    }


class Phase1StabilizationTest(unittest.TestCase):
    def test_system_config_serialization_does_not_return_raw_secret_values(self):
        module = _load_module(
            "system_config_stabilization_test",
            SYSTEM_CONFIG_PATH,
            _build_system_config_stubs(),
        )

        config = module.SystemExecutionConfig(
            title_model="title-model",
            translate_provider="gemini",
            translate_image_model="translate-image-model",
            translate_analysis_model="translate-analysis-model",
            quick_image_model="quick-image-model",
            batch_image_model="batch-image-model",
            relay_api_base="https://relay.example/v1",
            relay_api_key="relay-secret",
            relay_default_image_model="relay-image-model",
            gemini_api_key="gemini-secret",
            source="memory",
            persistence_enabled=False,
        )

        payload = module.serialize_system_execution_config(config)

        self.assertNotIn("relay_api_key", payload)
        self.assertNotIn("gemini_api_key", payload)
        self.assertEqual(payload["relay_api_key_preview"], "rela***cret")
        self.assertEqual(payload["gemini_api_key_preview"], "gemi***cret")

    def test_system_config_preserves_existing_secrets_when_submit_is_blank(self):
        module = _load_module(
            "system_config_preserve_secret_test",
            SYSTEM_CONFIG_PATH,
            _build_system_config_stubs(),
        )
        module.get_system_execution_config = lambda: module.SystemExecutionConfig(
            title_model="title-model",
            translate_provider="gemini",
            translate_image_model="translate-image-model",
            translate_analysis_model="translate-analysis-model",
            quick_image_model="quick-image-model",
            batch_image_model="batch-image-model",
            relay_api_base="https://relay.example/v1",
            relay_api_key="stored-relay-secret",
            relay_default_image_model="relay-image-model",
            gemini_api_key="stored-gemini-secret",
            source="memory",
            persistence_enabled=False,
        )

        payload = module._build_updated_config_payload(
            {
                "title_model": "next-title-model",
                "relay_api_key": "",
                "gemini_api_key": "",
            }
        )

        self.assertEqual(payload["title_model"], "next-title-model")
        self.assertEqual(payload["relay_api_key"], "stored-relay-secret")
        self.assertEqual(payload["gemini_api_key"], "stored-gemini-secret")

    def test_memory_job_repository_list_jobs_returns_summary_only(self):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "job_repository_stabilization_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.create_job(
            task_type="quick_generation",
            summary="Generate product hero image",
            status="completed",
            owner_id="user-1",
            payload={
                "summary": "Generate product hero image",
                "productInfo": "portable blender",
            },
            result={"outputs": [{"artifact_data_url": "data:image/png;base64,abc"}]},
        )

        items = repo.list_jobs(owner_id="user-1")

        self.assertEqual(len(items), 1)
        self.assertEqual(
            set(items[0].keys()),
            {"id", "status", "summary", "title", "icon", "created_at", "project"},
        )
        self.assertEqual(items[0]["summary"], "Generate product hero image")
        self.assertIsNone(items[0]["project"])


if __name__ == "__main__":
    unittest.main()
