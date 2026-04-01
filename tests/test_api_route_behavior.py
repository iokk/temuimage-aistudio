from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import os
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest


SYSTEM_CONFIG_PATH = Path("apps/api/core/system_config.py")
JOB_REPOSITORY_PATH = Path("apps/api/job_repository.py")
PERSONAL_CONFIG_PATH = Path("apps/api/core/personal_config.py")
SYSTEM_ROUTER_PATH = Path("apps/api/routers/system.py")
JOBS_ROUTER_PATH = Path("apps/api/routers/jobs.py")
PERSONAL_ROUTER_PATH = Path("apps/api/routers/personal.py")
PROJECTS_ROUTER_PATH = Path("apps/api/routers/projects.py")
TITLE_ROUTER_PATH = Path("apps/api/routers/title.py")


def _load_module(
    module_name: str, file_path: Path, stub_modules: dict[str, ModuleType]
):
    for name, module in stub_modules.items():
        sys.modules[name] = module
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_fastapi_stubs() -> dict[str, ModuleType]:
    fastapi = ModuleType("fastapi")
    fastapi_responses = ModuleType("fastapi.responses")

    class APIRouter:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def get(self, *args, **kwargs):
            del args, kwargs
            return lambda func: func

        def post(self, *args, **kwargs):
            del args, kwargs
            return lambda func: func

        def put(self, *args, **kwargs):
            del args, kwargs
            return lambda func: func

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class Response:
        def __init__(
            self,
            content: bytes | str = b"",
            status_code: int = 200,
            media_type: str | None = None,
            headers: dict[str, str] | None = None,
        ):
            if isinstance(content, str):
                self.body = content.encode()
            else:
                self.body = content
            self.status_code = status_code
            self.media_type = media_type
            self.headers = headers or {}

    fastapi.APIRouter = APIRouter
    fastapi.Depends = lambda dependency=None: dependency
    fastapi.HTTPException = HTTPException
    fastapi_responses.Response = Response

    pydantic = ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def model_dump(self):
            return dict(self.__dict__)

    pydantic.BaseModel = BaseModel
    pydantic.Field = lambda default=None, **kwargs: default

    return {
        "fastapi": fastapi,
        "fastapi.responses": fastapi_responses,
        "pydantic": pydantic,
    }


def _build_system_config_deps() -> dict[str, ModuleType]:
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
    config_module.get_settings = lambda: SimpleNamespace(
        app_name="XiaoBaiTu API",
        app_version="1.0.0",
        database_url="",
        redis_url="redis://localhost:6379/0",
        casdoor_issuer="",
        casdoor_client_id="",
        casdoor_client_secret="",
        auto_bootstrap_db=False,
    )

    db_models = ModuleType("apps.api.db.models")

    class _FakeSystemConfig:
        config_key = "system_execution"

    db_models.SystemConfig = _FakeSystemConfig

    return {
        **_build_fastapi_stubs(),
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.exc": sqlalchemy_exc,
        "sqlalchemy.orm": sqlalchemy_orm,
        "apps.api.core.config": config_module,
        "apps.api.db.models": db_models,
    }


def _build_job_repository_deps() -> dict[str, ModuleType]:
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
        **_build_fastapi_stubs(),
        "sqlalchemy": sqlalchemy,
        "sqlalchemy.exc": sqlalchemy_exc,
        "sqlalchemy.orm": sqlalchemy_orm,
        "apps.api.db.models": db_models,
        "temu_core.settings": settings_module,
    }


@dataclass(frozen=True)
class _Principal:
    user_id: str
    issuer: str
    subject: str
    email: str
    name: str
    email_verified: bool
    is_admin: bool
    is_team_member: bool


def _build_auth_module() -> ModuleType:
    auth_module = ModuleType("apps.api.core.auth")
    auth_module.Principal = _Principal
    auth_module.get_current_principal = lambda: _Principal(
        user_id="user-default",
        issuer="test",
        subject="sub-default",
        email="user@test.local",
        name="User",
        email_verified=True,
        is_admin=False,
        is_team_member=True,
    )
    auth_module.require_admin = lambda: _Principal(
        user_id="admin-default",
        issuer="test",
        subject="sub-admin",
        email="admin@test.local",
        name="Admin",
        email_verified=True,
        is_admin=True,
        is_team_member=True,
    )
    auth_module.require_team_member = lambda: _Principal(
        user_id="team-default",
        issuer="test",
        subject="sub-team",
        email="team@test.local",
        name="Team",
        email_verified=True,
        is_admin=False,
        is_team_member=True,
    )
    return auth_module


class ApiRouteBehaviorTest(unittest.TestCase):
    def test_title_context_route_reports_real_readiness(self):
        auth_module = _build_auth_module()
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        auth_module.get_current_principal = lambda: principal

        personal_config_module = ModuleType("apps.api.core.personal_config")
        personal_config_module.get_effective_execution_config_for_user = (
            lambda user_id: SimpleNamespace(
                title_model="gemini-3.1-pro",
                gemini_api_key="gemini-secret",
                relay_api_key="",
                relay_api_base="",
                source="personal:memory",
            )
        )
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = SimpleNamespace(
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_1",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                },
                "current_team": {
                    "organization_id": "org_xiaobaitu_team",
                    "organization_name": "XiaoBaiTu Team",
                    "organization_slug": "xiaobaitu-team",
                    "membership_role": "member",
                },
            }
        )
        task_execution_module = ModuleType("apps.api.task_execution")
        task_execution_module._resolve_title_provider = lambda config: "gemini"
        task_execution_module.DEFAULT_TITLE_TEMPLATE_KEY = "default"
        task_execution_module.IMAGE_TITLE_TEMPLATE_KEY = "image_analysis"
        task_execution_module.list_title_template_options = lambda: [
            {
                "key": "default",
                "name": "TEMU标准优化（中英双语）",
                "desc": "完整规则，中英双语输出，强调平台搜索与转化。",
            },
            {
                "key": "image_analysis",
                "name": "图片智能分析（中英双语）",
                "desc": "根据商品图片分析后生成中英双语标题。",
            },
        ]

        title_router_module = _load_module(
            "title_router_behavior_test",
            TITLE_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.core.auth": auth_module,
                "apps.api.core.personal_config": personal_config_module,
                "apps.api.job_repository": job_repository_module,
                "apps.api.task_execution": task_execution_module,
            },
        )

        payload = title_router_module.title_context(principal=principal)

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["default_model"], "gemini-3.1-pro")
        self.assertEqual(payload["default_template_key"], "default")
        self.assertEqual(payload["image_template_key"], "image_analysis")
        self.assertEqual(payload["provider"], "gemini")
        self.assertEqual(payload["config_source"], "personal:memory")
        self.assertEqual(
            payload["current_project"]["project_slug"], "default-workspace"
        )
        self.assertEqual(payload["template_options"][0]["key"], "default")
        self.assertTrue(payload["warnings"])
        self.assertIsNone(payload["blocking_reason"])

    def test_system_config_routes_keep_secrets_masked_and_preserve_blank_updates(self):
        os.environ.pop("DATABASE_URL", None)
        system_config_module = _load_module(
            "apps.api.core.system_config",
            SYSTEM_CONFIG_PATH,
            _build_system_config_deps(),
        )
        system_config_module.update_system_execution_config(
            {
                "title_model": "initial-title-model",
                "translate_provider": "gemini",
                "translate_image_model": "translate-image-model",
                "translate_analysis_model": "translate-analysis-model",
                "quick_image_model": "quick-image-model",
                "batch_image_model": "batch-image-model",
                "relay_api_base": "https://relay.example/v1",
                "relay_api_key": "relay-secret",
                "relay_default_image_model": "relay-image-model",
                "gemini_api_key": "gemini-secret",
            }
        )

        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.get_async_backend_meta = lambda: {
            "active_execution_backend": "inline",
            "preferred_execution_backend": "inline",
            "execution_fallback_reason": "",
            "execution_queue_ready": False,
            "execution_storage_compatible": True,
        }

        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = SimpleNamespace(
            get_backend_meta=lambda: {
                "active_backend": "memory",
                "preferred_backend": "memory",
                "fallback_reason": "",
                "persistence_ready": False,
            },
            get_account_team_state=lambda user_id: {
                "current_user": {
                    "id": user_id,
                    "email": "admin@test.local",
                    "name": "Admin",
                    "mode": "personal",
                    "issuer": "test",
                    "subject": "sub-admin-1",
                    "email_verified": True,
                    "last_login_at": "2026-03-31T00:00:00+00:00",
                },
                "current_team": {
                    "organization_id": "org_xiaobaitu_team",
                    "organization_name": "XiaoBaiTu Team",
                    "organization_slug": "xiaobaitu-team",
                    "membership_role": "admin",
                },
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                },
            },
        )

        router_module = _load_module(
            "system_router_behavior_test",
            SYSTEM_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.core.config": sys.modules["apps.api.core.config"],
                "apps.api.core.system_config": system_config_module,
                "apps.api.job_repository": job_repository_module,
            },
        )

        admin = _Principal(
            user_id="admin-1",
            issuer="test",
            subject="sub-admin-1",
            email="admin@test.local",
            name="Admin",
            email_verified=True,
            is_admin=True,
            is_team_member=True,
        )

        get_payload = router_module.system_config(_principal=admin)
        self.assertNotIn("relay_api_key", get_payload)
        self.assertNotIn("gemini_api_key", get_payload)
        self.assertEqual(get_payload["relay_api_key_preview"], "rela***cret")
        self.assertEqual(get_payload["gemini_api_key_preview"], "gemi***cret")

        request_payload = router_module.SystemExecutionConfigRequest(
            title_model="updated-title-model",
            translate_provider="gemini",
            translate_image_model="translate-image-model",
            translate_analysis_model="translate-analysis-model",
            quick_image_model="quick-image-model",
            batch_image_model="batch-image-model",
            relay_api_base="https://relay.example/v1",
            relay_api_key="",
            relay_default_image_model="relay-image-model",
            gemini_api_key="",
        )
        put_payload = router_module.system_config_update(
            request_payload, _principal=admin
        )

        self.assertEqual(put_payload["title_model"], "updated-title-model")
        self.assertNotIn("relay_api_key", put_payload)
        self.assertNotIn("gemini_api_key", put_payload)
        self.assertEqual(put_payload["relay_api_key_preview"], "rela***cret")
        self.assertEqual(put_payload["gemini_api_key_preview"], "gemi***cret")

        runtime_payload = router_module.system_runtime(principal=admin)
        self.assertEqual(runtime_payload["current_user"]["id"], "admin-1")
        self.assertTrue(runtime_payload["current_user"]["is_admin"])
        self.assertEqual(
            runtime_payload["current_team"]["organization_slug"], "xiaobaitu-team"
        )
        self.assertEqual(runtime_payload["current_team"]["membership_role"], "admin")
        self.assertEqual(
            runtime_payload["current_project"]["project_slug"], "default-workspace"
        )

    def test_personal_config_routes_keep_secrets_masked_and_preserve_blank_updates(
        self,
    ):
        os.environ.pop("DATABASE_URL", None)
        personal_config_module = _load_module(
            "apps.api.core.personal_config",
            PERSONAL_CONFIG_PATH,
            _build_system_config_deps(),
        )
        personal_config_module.update_personal_execution_config(
            "user-personal-1",
            {
                "use_personal_credentials": True,
                "provider": "relay",
                "relay_api_base": "https://relay.personal.example/v1",
                "relay_api_key": "relay-personal-secret",
                "relay_default_image_model": "seedream-4.0",
                "gemini_api_key": "gemini-personal-secret",
            },
        )

        personal_router_module = _load_module(
            "personal_router_behavior_test",
            PERSONAL_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.core.personal_config": personal_config_module,
            },
        )

        personal_principal = _Principal(
            user_id="user-personal-1",
            issuer="test",
            subject="sub-personal-1",
            email="solo@example.net",
            name="Solo",
            email_verified=True,
            is_admin=False,
            is_team_member=False,
        )

        get_payload = personal_router_module.personal_config(
            principal=personal_principal
        )
        self.assertNotIn("relay_api_key", get_payload)
        self.assertNotIn("gemini_api_key", get_payload)
        self.assertEqual(get_payload["relay_api_key_preview"], "rela***cret")
        self.assertEqual(get_payload["gemini_api_key_preview"], "gemi***cret")

        update_payload = personal_router_module.personal_config_update(
            personal_router_module.PersonalExecutionConfigRequest(
                use_personal_credentials=True,
                provider="gemini",
                relay_api_base="https://relay.personal.example/v1",
                relay_api_key="",
                relay_default_image_model="seedream-4.0",
                gemini_api_key="",
            ),
            principal=personal_principal,
        )
        self.assertTrue(update_payload["use_personal_credentials"])
        self.assertEqual(update_payload["provider"], "gemini")
        self.assertEqual(update_payload["relay_api_key_preview"], "rela***cret")
        self.assertEqual(update_payload["gemini_api_key_preview"], "gemi***cret")

    def test_jobs_list_route_returns_summary_only_items(self):
        os.environ.pop("DATABASE_URL", None)
        job_repository_module = _load_module(
            "apps.api.job_repository",
            JOB_REPOSITORY_PATH,
            _build_job_repository_deps(),
        )
        repo = job_repository_module.MemoryJobRepository()
        repo.create_job(
            task_type="quick_generation",
            summary="Generate hero image",
            status="completed",
            owner_id="user-1",
            project_id="project_xiaobaitu_default",
            payload={
                "summary": "Generate hero image",
                "productInfo": "portable blender",
                "projectName": "Default Workspace",
                "projectSlug": "default-workspace",
            },
            result={"outputs": [{"artifact_data_url": "data:image/png;base64,abc"}]},
        )
        repo.create_job(
            task_type="batch_generation",
            summary="Generate batch assets",
            status="queued",
            owner_id="user-2",
            payload={"summary": "Generate batch assets"},
            result={"outputs": [{"artifact_data_url": "data:image/png;base64,def"}]},
        )

        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda *args, **kwargs: "inline"
        async_dispatcher.get_async_backend_meta = lambda: {
            "active_execution_backend": "inline",
            "preferred_execution_backend": "inline",
            "execution_fallback_reason": "",
            "execution_queue_ready": False,
            "execution_storage_compatible": True,
        }

        jobs_router_module = _load_module(
            "jobs_router_behavior_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )

        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        payload = jobs_router_module.jobs_list(principal=principal)

        self.assertEqual(payload["pending_count"], 0)
        self.assertEqual(payload["total"], 1)
        self.assertIn("active_backend", payload)
        self.assertIn("active_execution_backend", payload)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(
            set(payload["items"][0].keys()),
            {"id", "status", "summary", "title", "icon", "created_at", "project"},
        )
        self.assertEqual(payload["items"][0]["summary"], "Generate hero image")
        self.assertEqual(
            payload["items"][0]["project"]["project_slug"],
            "default-workspace",
        )

        filtered = jobs_router_module.jobs_list(
            project_id="project_xiaobaitu_default",
            principal=principal,
        )
        self.assertEqual(filtered["total"], 1)

        detail = jobs_router_module.jobs_detail("job-1", principal=principal)
        self.assertEqual(
            detail["job"]["project"]["project_slug"],
            "default-workspace",
        )

    def test_jobs_submit_injects_current_project_into_job_payload(self):
        create_calls: list[dict[str, object]] = []
        dispatch_calls: list[dict[str, object]] = []
        repo_stub = SimpleNamespace(
            create_job=lambda **kwargs: (
                create_calls.append(kwargs)
                or {"id": "job-1", "status": kwargs.get("status", "completed")}
            ),
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                }
            },
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda job_id, task_type, payload: (
            dispatch_calls.append(
                {"job_id": job_id, "task_type": task_type, "payload": payload}
            )
            or "inline"
        )
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_project_behavior_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        request = jobs_router_module.JobCreateRequest(
            task_type="title_generation",
            summary="标题优化 · 3 条候选",
            status="completed",
            payload={"productInfo": "portable blender"},
            result={},
        )

        response = jobs_router_module.jobs_submit(request, principal=principal)

        self.assertEqual(response["job"]["id"], "job-1")
        self.assertEqual(create_calls[0]["project_id"], "project_xiaobaitu_default")
        self.assertEqual(
            create_calls[0]["payload"]["projectSlug"],
            "default-workspace",
        )

        async_request = jobs_router_module.JobCreateRequest(
            task_type="title_generation",
            summary="标题优化 · 3 条候选",
            payload={"productInfo": "portable blender"},
            result={},
        )
        jobs_router_module.jobs_submit_async(async_request, principal=principal)
        self.assertEqual(
            dispatch_calls[0]["payload"]["projectId"],
            "project_xiaobaitu_default",
        )

    def test_jobs_submit_supports_personal_current_project_context(self):
        create_calls: list[dict[str, object]] = []
        repo_stub = SimpleNamespace(
            create_job=lambda **kwargs: (
                create_calls.append(kwargs)
                or {"id": "job-personal-1", "status": kwargs.get("status", "completed")}
            ),
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_personal_user_1",
                    "project_name": "Personal Workspace",
                    "project_slug": "personal-workspace-user-1",
                    "project_status": "active",
                },
                "current_team": None,
            },
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda *args, **kwargs: "inline"
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_personal_project_behavior_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-personal-1",
            issuer="test",
            subject="sub-personal-1",
            email="solo@example.net",
            name="Solo",
            email_verified=True,
            is_admin=False,
            is_team_member=False,
        )
        request = jobs_router_module.JobCreateRequest(
            task_type="title_generation",
            summary="标题优化 · 3 条候选",
            payload={"productInfo": "portable blender"},
            result={},
        )

        response = jobs_router_module.jobs_submit_async(request, principal=principal)

        self.assertEqual(response["job"]["id"], "job-personal-1")
        self.assertEqual(create_calls[0]["project_id"], "project_personal_user_1")
        self.assertEqual(
            create_calls[0]["payload"]["projectName"], "Personal Workspace"
        )
        self.assertEqual(
            create_calls[0]["payload"]["projectSlug"],
            "personal-workspace-user-1",
        )

    def test_jobs_submit_recovers_current_project_via_ensure_project_state(self):
        create_calls: list[dict[str, object]] = []
        dispatch_calls: list[dict[str, object]] = []
        account_states = [
            {"current_project": None},
            {
                "current_project": {
                    "project_id": "project_summer_campaign",
                    "project_name": "Summer Campaign",
                    "project_slug": "summer-campaign",
                    "project_status": "active",
                }
            },
            {
                "current_project": {
                    "project_id": "project_summer_campaign",
                    "project_name": "Summer Campaign",
                    "project_slug": "summer-campaign",
                    "project_status": "active",
                }
            },
        ]
        ensure_calls: list[str] = []

        def get_account_team_state(user_id: str):
            del user_id
            return account_states.pop(0)

        repo_stub = SimpleNamespace(
            create_job=lambda **kwargs: (
                create_calls.append(kwargs)
                or {
                    "id": f"job-{len(create_calls)}",
                    "status": kwargs.get("status", "completed"),
                }
            ),
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=get_account_team_state,
            ensure_project_state=lambda **kwargs: (
                ensure_calls.append(kwargs["user_id"])
                or {
                    "current_project": {
                        "project_id": "project_summer_campaign",
                        "project_name": "Summer Campaign",
                        "project_slug": "summer-campaign",
                        "project_status": "active",
                    }
                }
            ),
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda job_id, task_type, payload: (
            dispatch_calls.append(
                {"job_id": job_id, "task_type": task_type, "payload": payload}
            )
            or "inline"
        )
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_project_recovery_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )

        sync_request = jobs_router_module.JobCreateRequest(
            task_type="quick_generation",
            summary="快速出图 · 主图强化",
            payload={"productInfo": "portable blender"},
            result={},
        )
        async_request = jobs_router_module.JobCreateRequest(
            task_type="batch_generation",
            summary="批量出图 · 2 种类型",
            payload={"productInfo": "portable blender"},
            result={},
        )

        sync_response = jobs_router_module.jobs_submit(
            sync_request, principal=principal
        )
        async_response = jobs_router_module.jobs_submit_async(
            async_request,
            principal=principal,
        )

        self.assertEqual(ensure_calls, ["user-1"])
        self.assertEqual(sync_response["job"]["id"], "job-1")
        self.assertEqual(async_response["job"]["id"], "job-2")
        self.assertEqual(create_calls[0]["project_id"], "project_summer_campaign")
        self.assertEqual(create_calls[0]["payload"]["projectName"], "Summer Campaign")
        self.assertEqual(create_calls[1]["payload"]["projectSlug"], "summer-campaign")
        self.assertEqual(
            dispatch_calls[0]["payload"]["projectId"], "project_summer_campaign"
        )

    def test_jobs_submit_returns_400_when_current_project_cannot_be_resolved(self):
        repo_stub = SimpleNamespace(
            create_job=lambda **kwargs: kwargs,
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=lambda user_id: {"current_project": None},
            ensure_project_state=lambda **kwargs: {"current_project": None},
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda *args, **kwargs: "inline"
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_project_missing_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        request = jobs_router_module.JobCreateRequest(
            task_type="title_generation",
            summary="标题优化 · 3 条候选",
            payload={"productInfo": "portable blender"},
            result={},
        )

        with self.assertRaises(jobs_router_module.HTTPException) as sync_context:
            jobs_router_module.jobs_submit(request, principal=principal)
        self.assertEqual(sync_context.exception.status_code, 400)

        with self.assertRaises(jobs_router_module.HTTPException) as async_context:
            jobs_router_module.jobs_submit_async(request, principal=principal)
        self.assertEqual(async_context.exception.status_code, 400)

    def test_translate_async_submit_sanitizes_stored_payload_and_exports_zip(self):
        create_calls: list[dict[str, object]] = []
        dispatch_calls: list[dict[str, object]] = []
        stored_job = {
            "id": "job-translate-1",
            "status": "queued",
            "task_type": "image_translate",
            "summary": "图片翻译 · English · 2 张",
            "page": "图片翻译",
            "title": "图片翻译",
            "icon": "🌐",
            "payload": {},
            "result": {
                "outputs": [
                    {
                        "id": "img-1",
                        "label": "翻译结果 1",
                        "filename": "translated-1.png",
                        "artifact_data_url": "data:image/png;base64,ZmFrZQ==",
                    }
                ]
            },
            "project": {
                "project_id": "project_xiaobaitu_default",
                "project_name": "Default Workspace",
                "project_slug": "default-workspace",
                "project_status": "active",
            },
        }

        def create_job(**kwargs):
            create_calls.append(kwargs)
            return {"id": "job-translate-1", "status": kwargs.get("status", "queued")}

        repo_stub = SimpleNamespace(
            create_job=create_job,
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                }
            },
            get_job=lambda job_id, **kwargs: (
                stored_job if job_id == "job-translate-1" else None
            ),
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda job_id, task_type, payload: (
            dispatch_calls.append(
                {"job_id": job_id, "task_type": task_type, "payload": payload}
            )
            or "inline"
        )
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_translate_payload_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        request = jobs_router_module.JobCreateRequest(
            task_type="image_translate",
            summary="图片翻译 · English · 2 张",
            payload={
                "sourceLang": "auto",
                "targetLang": "English",
                "uploadItems": [
                    {
                        "id": "img-1",
                        "rawName": "first.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": "data:image/png;base64,AAAA",
                    },
                    {
                        "id": "img-2",
                        "rawName": "second.png",
                        "mimeType": "image/png",
                        "sizeBytes": 2048,
                        "imageDataUrl": "data:image/png;base64,BBBB",
                    },
                ],
            },
            result={},
        )

        response = jobs_router_module.jobs_submit_async(request, principal=principal)

        self.assertEqual(response["job"]["id"], "job-translate-1")
        stored_upload = create_calls[0]["payload"]["uploadItems"][0]
        self.assertNotIn("imageDataUrl", stored_upload)
        self.assertEqual(stored_upload["rawName"], "first.png")
        self.assertEqual(
            dispatch_calls[0]["payload"]["uploadItems"][0]["imageDataUrl"],
            "data:image/png;base64,AAAA",
        )
        self.assertEqual(create_calls[0]["payload"]["projectSlug"], "default-workspace")

        export_response = jobs_router_module.jobs_translate_export_zip(
            "job-translate-1",
            principal=principal,
        )
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response.media_type, "application/zip")
        self.assertIn(
            "attachment; filename=translate-job-translate-1.zip",
            export_response.headers["Content-Disposition"],
        )
        self.assertTrue(export_response.body)

    def test_title_async_submit_sanitizes_upload_items_for_storage(self):
        create_calls: list[dict[str, object]] = []
        dispatch_calls: list[dict[str, object]] = []

        def create_job(**kwargs):
            create_calls.append(kwargs)
            return {"id": "job-title-1", "status": kwargs.get("status", "queued")}

        repo_stub = SimpleNamespace(
            create_job=create_job,
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                }
            },
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda job_id, task_type, payload: (
            dispatch_calls.append(
                {"job_id": job_id, "task_type": task_type, "payload": payload}
            )
            or "inline"
        )
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_title_payload_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        request = jobs_router_module.JobCreateRequest(
            task_type="title_generation",
            summary="标题优化 · 图片分析",
            payload={
                "uploadItems": [
                    {
                        "id": "img-1",
                        "rawName": "first.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": "data:image/png;base64,AAAA",
                    }
                ],
                "productInfo": "portable blender",
            },
            result={},
        )

        response = jobs_router_module.jobs_submit_async(request, principal=principal)

        self.assertEqual(response["job"]["id"], "job-title-1")
        stored_upload = create_calls[0]["payload"]["uploadItems"][0]
        self.assertNotIn("imageDataUrl", stored_upload)
        self.assertEqual(stored_upload["rawName"], "first.png")
        self.assertEqual(
            dispatch_calls[0]["payload"]["uploadItems"][0]["imageDataUrl"],
            "data:image/png;base64,AAAA",
        )
        self.assertEqual(create_calls[0]["payload"]["uploadCount"], 1)
        self.assertEqual(create_calls[0]["payload"]["projectSlug"], "default-workspace")

    def test_translate_export_zip_rejects_non_translate_jobs(self):
        repo_stub = SimpleNamespace(
            get_job=lambda job_id, **kwargs: {
                "id": job_id,
                "task_type": "quick_generation",
                "result": {"outputs": []},
            },
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda *args, **kwargs: "inline"
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_translate_export_reject_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )

        with self.assertRaises(jobs_router_module.HTTPException) as context:
            jobs_router_module.jobs_translate_export_zip(
                "job-quick-1", principal=principal
            )
        self.assertEqual(context.exception.status_code, 400)

    def test_quick_and_batch_async_submit_sanitize_upload_items_and_export_zip(self):
        create_calls: list[dict[str, object]] = []
        dispatch_calls: list[dict[str, object]] = []
        stored_jobs = {
            "job-quick-1": {
                "id": "job-quick-1",
                "task_type": "quick_generation",
                "result": {
                    "outputs": [
                        {
                            "id": "quick-1",
                            "filename": "selling-point-1.png",
                            "artifact_data_url": "data:image/png;base64,QUJD",
                        }
                    ]
                },
            },
            "job-batch-1": {
                "id": "job-batch-1",
                "task_type": "batch_generation",
                "result": {
                    "outputs": [
                        {
                            "id": "batch-1",
                            "filename": "main-1.png",
                            "artifact_data_url": "data:image/png;base64,REVG",
                        }
                    ]
                },
            },
        }

        def create_job(**kwargs):
            create_calls.append(kwargs)
            return {
                "id": (
                    "job-quick-1"
                    if kwargs["task_type"] == "quick_generation"
                    else "job-batch-1"
                ),
                "status": kwargs.get("status", "queued"),
            }

        repo_stub = SimpleNamespace(
            create_job=create_job,
            count_pending_jobs=lambda **kwargs: 0,
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                }
            },
            get_job=lambda job_id, **kwargs: stored_jobs.get(job_id),
        )
        async_dispatcher = ModuleType("apps.api.async_dispatcher")
        async_dispatcher.dispatch_preview_job = lambda job_id, task_type, payload: (
            dispatch_calls.append(
                {"job_id": job_id, "task_type": task_type, "payload": payload}
            )
            or "inline"
        )
        async_dispatcher.get_async_backend_meta = lambda: {}
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub

        jobs_router_module = _load_module(
            "jobs_router_quick_batch_upload_test",
            JOBS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.async_dispatcher": async_dispatcher,
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )
        principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )

        quick_request = jobs_router_module.JobCreateRequest(
            task_type="quick_generation",
            summary="快速出图 · 卖点图 · 2 张",
            payload={
                "imageType": "selling_point",
                "uploadItems": [
                    {
                        "id": "img-1",
                        "rawName": "hero.png",
                        "mimeType": "image/png",
                        "sizeBytes": 1024,
                        "imageDataUrl": "data:image/png;base64,AAAA",
                    }
                ],
            },
            result={},
        )
        batch_request = jobs_router_module.JobCreateRequest(
            task_type="batch_generation",
            summary="批量出图 · 2 种类型",
            payload={
                "selectedTypes": ["main", "feature"],
                "uploadItems": [
                    {
                        "id": "img-2",
                        "rawName": "detail.png",
                        "mimeType": "image/png",
                        "sizeBytes": 2048,
                        "imageDataUrl": "data:image/png;base64,BBBB",
                    }
                ],
            },
            result={},
        )

        jobs_router_module.jobs_submit_async(quick_request, principal=principal)
        jobs_router_module.jobs_submit_async(batch_request, principal=principal)

        self.assertNotIn("imageDataUrl", create_calls[0]["payload"]["uploadItems"][0])
        self.assertNotIn("imageDataUrl", create_calls[1]["payload"]["uploadItems"][0])
        self.assertEqual(
            dispatch_calls[0]["payload"]["uploadItems"][0]["imageDataUrl"],
            "data:image/png;base64,AAAA",
        )
        self.assertEqual(
            dispatch_calls[1]["payload"]["uploadItems"][0]["imageDataUrl"],
            "data:image/png;base64,BBBB",
        )
        self.assertEqual(create_calls[0]["payload"]["projectSlug"], "default-workspace")
        self.assertEqual(create_calls[1]["payload"]["projectSlug"], "default-workspace")

        quick_export = jobs_router_module.jobs_export_artifacts_zip(
            "job-quick-1",
            principal=principal,
        )
        batch_export = jobs_router_module.jobs_export_artifacts_zip(
            "job-batch-1",
            principal=principal,
        )
        self.assertEqual(quick_export.media_type, "application/zip")
        self.assertEqual(batch_export.media_type, "application/zip")
        self.assertIn("job-quick-1", quick_export.headers["Content-Disposition"])
        self.assertIn("job-batch-1", batch_export.headers["Content-Disposition"])
        self.assertTrue(quick_export.body)
        self.assertTrue(batch_export.body)

    def test_projects_current_routes_read_and_update_project(self):
        update_calls: list[dict[str, object]] = []
        create_calls: list[dict[str, object]] = []
        select_calls: list[dict[str, object]] = []
        repo_stub = SimpleNamespace(
            list_projects=lambda user_id: {
                "items": [
                    {
                        "project_id": "project_xiaobaitu_default",
                        "project_name": "Default Workspace",
                        "project_slug": "default-workspace",
                        "project_status": "active",
                    },
                    {
                        "project_id": "project_summer_campaign",
                        "project_name": "Summer Campaign",
                        "project_slug": "summer-campaign",
                        "project_status": "active",
                    },
                ],
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                },
            },
            get_account_team_state=lambda user_id: {
                "current_project": {
                    "project_id": "project_xiaobaitu_default",
                    "project_name": "Default Workspace",
                    "project_slug": "default-workspace",
                    "project_status": "active",
                }
            },
            update_current_project=lambda **kwargs: (
                update_calls.append(kwargs)
                or {
                    "current_project": {
                        "project_id": "project_xiaobaitu_default",
                        "project_name": kwargs["name"],
                        "project_slug": "default-workspace",
                        "project_status": "active",
                    }
                }
            ),
            create_project=lambda **kwargs: (
                create_calls.append(kwargs)
                or {
                    "items": [
                        {
                            "project_id": "project_xiaobaitu_default",
                            "project_name": "Default Workspace",
                            "project_slug": "default-workspace",
                            "project_status": "active",
                        },
                        {
                            "project_id": "project_new_workspace",
                            "project_name": kwargs["name"],
                            "project_slug": "new-workspace",
                            "project_status": "active",
                        },
                    ],
                    "current_project": {
                        "project_id": "project_new_workspace",
                        "project_name": kwargs["name"],
                        "project_slug": "new-workspace",
                        "project_status": "active",
                    },
                }
            ),
            select_current_project=lambda **kwargs: (
                select_calls.append(kwargs)
                or {
                    "items": [
                        {
                            "project_id": "project_xiaobaitu_default",
                            "project_name": "Default Workspace",
                            "project_slug": "default-workspace",
                            "project_status": "active",
                        },
                        {
                            "project_id": kwargs["project_id"],
                            "project_name": "Summer Campaign",
                            "project_slug": "summer-campaign",
                            "project_status": "active",
                        },
                    ],
                    "current_project": {
                        "project_id": kwargs["project_id"],
                        "project_name": "Summer Campaign",
                        "project_slug": "summer-campaign",
                        "project_status": "active",
                    },
                }
            ),
        )
        job_repository_module = ModuleType("apps.api.job_repository")
        job_repository_module.job_repository = repo_stub
        project_router_module = _load_module(
            "projects_router_behavior_test",
            PROJECTS_ROUTER_PATH,
            {
                **_build_fastapi_stubs(),
                "apps.api.core.auth": _build_auth_module(),
                "apps.api.job_repository": job_repository_module,
            },
        )

        team_principal = _Principal(
            user_id="user-1",
            issuer="test",
            subject="sub-user-1",
            email="user@test.local",
            name="User",
            email_verified=True,
            is_admin=False,
            is_team_member=True,
        )
        admin_principal = _Principal(
            user_id="admin-1",
            issuer="test",
            subject="sub-admin-1",
            email="admin@test.local",
            name="Admin",
            email_verified=True,
            is_admin=True,
            is_team_member=True,
        )

        get_payload = project_router_module.current_project(principal=team_principal)
        self.assertEqual(get_payload["project"]["project_slug"], "default-workspace")

        list_payload = project_router_module.list_projects(principal=team_principal)
        self.assertEqual(len(list_payload["items"]), 2)

        request = project_router_module.ProjectUpdateRequest(
            name="Spring Campaign Workspace"
        )
        put_payload = project_router_module.update_current_project(
            request,
            principal=admin_principal,
        )
        self.assertEqual(update_calls[0]["user_id"], "admin-1")
        self.assertEqual(
            put_payload["project"]["project_name"],
            "Spring Campaign Workspace",
        )

        with self.assertRaises(project_router_module.HTTPException) as context:
            project_router_module.update_current_project(
                project_router_module.ProjectUpdateRequest(name="   "),
                principal=admin_principal,
            )
        self.assertEqual(context.exception.status_code, 400)

        create_payload = project_router_module.create_project(
            project_router_module.ProjectCreateRequest(name="New Workspace"),
            principal=admin_principal,
        )
        self.assertEqual(create_calls[0]["name"], "New Workspace")
        self.assertEqual(
            create_payload["current_project"]["project_slug"],
            "new-workspace",
        )

        select_payload = project_router_module.select_current_project(
            project_router_module.ProjectSelectRequest(
                project_id="project_summer_campaign"
            ),
            principal=team_principal,
        )
        self.assertEqual(select_calls[0]["project_id"], "project_summer_campaign")
        self.assertEqual(
            select_payload["current_project"]["project_slug"],
            "summer-campaign",
        )

    def test_resilient_repository_fallback_forwards_scope_and_project_args(self):
        os.environ.pop("DATABASE_URL", None)
        job_repository_module = _load_module(
            "apps.api.job_repository",
            JOB_REPOSITORY_PATH,
            _build_job_repository_deps(),
        )

        fallback = job_repository_module.MemoryJobRepository()
        fallback.create_job(
            task_type="quick_generation",
            summary="Default workspace hero image",
            status="queued",
            owner_id="user-1",
            project_id="project_xiaobaitu_default",
            payload={
                "summary": "Default workspace hero image",
                "projectName": "Default Workspace",
                "projectSlug": "default-workspace",
            },
        )
        target_job = fallback.create_job(
            task_type="quick_generation",
            summary="Summer campaign hero image",
            status="running",
            owner_id="user-1",
            project_id="project_summer_campaign",
            payload={
                "summary": "Summer campaign hero image",
                "projectName": "Summer Campaign",
                "projectSlug": "summer-campaign",
            },
        )
        fallback.create_job(
            task_type="quick_generation",
            summary="Other user image",
            status="queued",
            owner_id="user-2",
            project_id="project_summer_campaign",
            payload={
                "summary": "Other user image",
                "projectName": "Summer Campaign",
                "projectSlug": "summer-campaign",
            },
        )

        class _FailingPrimary:
            def list_jobs(self, **kwargs):
                raise RuntimeError(f"list failed for {kwargs['owner_id']}")

            def count_pending_jobs(self, **kwargs):
                raise RuntimeError(f"count failed for {kwargs['project_id']}")

            def get_job(self, job_id, **kwargs):
                raise RuntimeError(f"get failed for {job_id}:{kwargs['owner_id']}")

            def update_job(self, job_id, **kwargs):
                raise RuntimeError(f"update failed for {job_id}:{kwargs['status']}")

        repo = job_repository_module.ResilientJobRepository(
            preferred_backend="database",
            primary=_FailingPrimary(),
            fallback=fallback,
        )

        jobs = repo.list_jobs(owner_id="user-1", project_id="project_summer_campaign")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], target_job["id"])
        self.assertEqual(jobs[0]["project"]["project_slug"], "summer-campaign")

        detail = repo.get_job(target_job["id"], owner_id="user-1")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["project"]["project_id"], "project_summer_campaign")

        updated = repo.update_job(
            target_job["id"],
            status="completed",
            owner_id="user-1",
            result={"outputs": [{"artifact_data_url": "data:image/png;base64,abc"}]},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["status"], "completed")
        self.assertEqual(updated["project"]["project_name"], "Summer Campaign")

        pending = repo.count_pending_jobs(
            owner_id="user-1",
            project_id="project_summer_campaign",
        )
        self.assertEqual(pending, 0)
        backend_meta = repo.get_backend_meta()
        self.assertEqual(backend_meta["active_backend"], "memory")
        self.assertIn("list failed for user-1", backend_meta["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
