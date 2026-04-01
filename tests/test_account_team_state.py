from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import os
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest


JOB_REPOSITORY_PATH = Path("apps/api/job_repository.py")
AUTH_PATH = Path("apps/api/core/auth.py")


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


def _build_auth_stubs(repo) -> dict[str, ModuleType]:
    jwt_module = ModuleType("jwt")
    jwt_module.PyJWKClient = object
    jwt_module.InvalidTokenError = Exception
    jwt_module.decode = lambda *args, **kwargs: {}

    fastapi = ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    fastapi.Depends = lambda dependency=None: dependency
    fastapi.HTTPException = HTTPException
    fastapi.status = SimpleNamespace(
        HTTP_503_SERVICE_UNAVAILABLE=503,
        HTTP_401_UNAUTHORIZED=401,
        HTTP_403_FORBIDDEN=403,
    )

    fastapi_security = ModuleType("fastapi.security")
    fastapi_security.HTTPAuthorizationCredentials = object

    class HTTPBearer:
        def __init__(self, auto_error: bool = False):
            self.auto_error = auto_error

    fastapi_security.HTTPBearer = HTTPBearer

    config_module = ModuleType("apps.api.core.config")
    config_module.AppSettings = object
    config_module.get_settings = lambda: SimpleNamespace(
        casdoor_issuer="",
        casdoor_client_id="",
        casdoor_client_secret="",
        casdoor_api_audience="",
    )

    job_repository_module = ModuleType("apps.api.job_repository")
    job_repository_module.job_repository = repo

    return {
        "jwt": jwt_module,
        "fastapi": fastapi,
        "fastapi.security": fastapi_security,
        "apps.api.core.config": config_module,
        "apps.api.job_repository": job_repository_module,
    }


class AccountTeamStateTest(unittest.TestCase):
    def test_memory_repository_provisions_personal_state_without_team(self):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "account_personal_job_repository_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.upsert_user(
            user_id="user-personal-1",
            email="solo@example.net",
            name="Solo",
            issuer="test",
            subject="sub-personal-1",
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )

        state = repo.ensure_personal_state(user_id="user-personal-1")

        self.assertEqual(state["current_user"]["id"], "user-personal-1")
        self.assertIsNone(state["current_team"])
        self.assertEqual(state["current_project"]["project_name"], "Personal Workspace")
        self.assertTrue(
            state["current_project"]["project_slug"].startswith("personal-workspace")
        )

    def test_personal_state_prefers_personal_membership_over_stale_team_membership(
        self,
    ):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "account_personal_membership_preference_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.upsert_user(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            issuer="test",
            subject="sub-1",
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )
        repo.ensure_team_state(user_id="user-1", is_admin=False)

        state = repo.ensure_personal_state(user_id="user-1")

        self.assertEqual(state["current_user"]["mode"], "personal")
        self.assertIsNone(state["current_team"])
        self.assertEqual(state["current_project"]["project_name"], "Personal Workspace")

    def test_team_state_prefers_team_membership_over_stale_personal_membership(self):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "account_team_membership_preference_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.upsert_user(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            issuer="test",
            subject="sub-1",
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )
        repo.ensure_personal_state(user_id="user-1")

        state = repo.ensure_team_state(user_id="user-1", is_admin=False)

        self.assertEqual(state["current_user"]["mode"], "team")
        self.assertIsNotNone(state["current_team"])
        self.assertEqual(state["current_team"]["organization_slug"], "xiaobaitu-team")
        self.assertEqual(state["current_project"]["project_slug"], "default-workspace")

    def test_memory_repository_persists_default_team_state(self):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "account_team_job_repository_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.upsert_user(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            issuer="test",
            subject="sub-1",
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )

        state = repo.ensure_team_state(user_id="user-1", is_admin=True)

        self.assertEqual(state["current_user"]["id"], "user-1")
        self.assertEqual(state["current_team"]["organization_slug"], "xiaobaitu-team")
        self.assertEqual(state["current_team"]["membership_role"], "admin")
        self.assertEqual(state["current_project"]["project_slug"], "default-workspace")

    def test_memory_repository_updates_current_project_name(self):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "account_team_project_update_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.upsert_user(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            issuer="test",
            subject="sub-1",
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )
        repo.ensure_team_state(user_id="user-1", is_admin=True)

        state = repo.update_current_project(
            user_id="user-1",
            name="Spring Campaign Workspace",
        )

        self.assertEqual(
            state["current_project"]["project_name"],
            "Spring Campaign Workspace",
        )

    def test_memory_repository_can_create_and_select_projects(self):
        os.environ.pop("DATABASE_URL", None)
        module = _load_module(
            "account_team_project_selection_test",
            JOB_REPOSITORY_PATH,
            _build_job_repository_stubs(),
        )
        repo = module.MemoryJobRepository()
        repo.upsert_user(
            user_id="user-1",
            email="member@example.com",
            name="Member",
            issuer="test",
            subject="sub-1",
            email_verified=True,
            last_login_at=datetime.now(timezone.utc),
        )
        repo.ensure_team_state(user_id="user-1", is_admin=True)

        created = repo.create_project(user_id="user-1", name="Summer Campaign")
        self.assertEqual(created["current_project"]["project_name"], "Summer Campaign")
        self.assertEqual(len(created["items"]), 2)

        default_project_id = next(
            item["project_id"]
            for item in created["items"]
            if item["project_slug"] == "default-workspace"
        )
        selected = repo.select_current_project(
            user_id="user-1",
            project_id=default_project_id,
        )
        self.assertEqual(
            selected["current_project"]["project_slug"],
            "default-workspace",
        )

        renamed = repo.update_current_project(
            user_id="user-1",
            name="Recovered Default Workspace",
        )
        self.assertEqual(
            renamed["current_project"]["project_name"],
            "Recovered Default Workspace",
        )

    def test_build_principal_ensures_team_state_for_team_member(self):
        os.environ["TEAM_ALLOWED_EMAIL_DOMAINS"] = "example.com"
        repo = SimpleNamespace(
            upsert_calls=[],
            ensure_calls=[],
        )
        repo.upsert_user = lambda **kwargs: repo.upsert_calls.append(kwargs)
        repo.ensure_team_state = lambda **kwargs: repo.ensure_calls.append(kwargs)

        module = _load_module(
            "account_team_auth_test",
            AUTH_PATH,
            _build_auth_stubs(repo),
        )

        principal = module._build_principal(
            {
                "iss": "issuer",
                "sub": "subject",
                "email": "member@example.com",
                "name": "Member",
                "email_verified": True,
            }
        )

        self.assertTrue(principal.is_team_member)
        self.assertEqual(len(repo.upsert_calls), 1)
        self.assertEqual(len(repo.ensure_calls), 1)
        self.assertEqual(repo.ensure_calls[0]["user_id"], principal.user_id)
        self.assertFalse(repo.ensure_calls[0]["is_admin"])

    def test_build_principal_ensures_personal_state_for_non_team_user(self):
        os.environ["TEAM_ALLOWED_EMAIL_DOMAINS"] = "example.com"
        repo = SimpleNamespace(
            upsert_calls=[],
            ensure_team_calls=[],
            ensure_personal_calls=[],
        )
        repo.upsert_user = lambda **kwargs: repo.upsert_calls.append(kwargs)
        repo.ensure_team_state = lambda **kwargs: repo.ensure_team_calls.append(kwargs)
        repo.ensure_personal_state = lambda **kwargs: repo.ensure_personal_calls.append(
            kwargs
        )

        module = _load_module(
            "account_personal_auth_test",
            AUTH_PATH,
            _build_auth_stubs(repo),
        )

        principal = module._build_principal(
            {
                "iss": "issuer",
                "sub": "subject",
                "email": "solo@example.net",
                "name": "Solo",
                "email_verified": True,
            }
        )

        self.assertFalse(principal.is_team_member)
        self.assertEqual(len(repo.upsert_calls), 1)
        self.assertEqual(repo.ensure_team_calls, [])
        self.assertEqual(len(repo.ensure_personal_calls), 1)
        self.assertEqual(repo.ensure_personal_calls[0]["user_id"], principal.user_id)

    def test_build_principal_uses_persisted_user_id_from_repository(self):
        os.environ["TEAM_ALLOWED_EMAIL_DOMAINS"] = "example.com"
        repo = SimpleNamespace(
            ensure_calls=[],
        )
        repo.upsert_user = lambda **kwargs: {"id": "persisted-user-42"}
        repo.ensure_team_state = lambda **kwargs: repo.ensure_calls.append(kwargs)

        module = _load_module(
            "account_team_auth_persisted_id_test",
            AUTH_PATH,
            _build_auth_stubs(repo),
        )

        principal = module._build_principal(
            {
                "iss": "issuer",
                "sub": "subject",
                "email": "member@example.com",
                "name": "Member",
                "email_verified": True,
            }
        )

        self.assertEqual(principal.user_id, "persisted-user-42")
        self.assertEqual(repo.ensure_calls[0]["user_id"], "persisted-user-42")


if __name__ == "__main__":
    unittest.main()
