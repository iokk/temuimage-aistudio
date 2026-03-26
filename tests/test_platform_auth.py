from __future__ import annotations

from pathlib import Path
import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from temu_core.auth import (
    authenticate_local_user,
    backup_and_delete_local_user,
    ensure_local_user,
    list_secure_api_key_previews,
    list_user_backups,
    load_secure_api_keys_payload,
    save_secure_api_keys_payload,
    set_local_user_status,
    set_registration_open,
)
from temu_core.models import Base
from temu_core.settings import get_platform_settings


class PlatformAuthTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, future=True)
        get_platform_settings.cache_clear()

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()
        os.environ.pop("PLATFORM_ENCRYPTION_KEY", None)
        get_platform_settings.cache_clear()

    def test_registration_lifecycle_and_backup(self):
        with self.Session() as session:
            set_registration_open(session, True, actor_label="test-admin")
            user = ensure_local_user(
                session,
                username="alice",
                password="pass1234",
                display_name="Alice",
                email="alice@example.com",
                actor_label="test-admin",
            )
            user_id = user.id
            session.commit()

        with self.Session() as session:
            authed = authenticate_local_user(session, "alice", "pass1234")
            self.assertEqual(authed.username, "alice")
            set_local_user_status(
                session,
                user_id=user_id,
                status="disabled",
                actor_label="test-admin",
                reason="pause",
            )
            session.commit()

        with self.Session() as session:
            with self.assertRaises(ValueError):
                authenticate_local_user(session, "alice", "pass1234")
            backup = backup_and_delete_local_user(
                session,
                user_id=user_id,
                actor_label="test-admin",
                reason="cleanup",
            )
            session.commit()
            backups = list_user_backups(session)
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].id, backup.id)
            self.assertEqual(backups[0].username, "alice")

    def test_secure_api_key_roundtrip(self):
        os.environ["PLATFORM_ENCRYPTION_KEY"] = "unit-test-secret"
        get_platform_settings.cache_clear()
        payload = {
            "keys": [
                {
                    "key": "AIzaFakeKey1234567890",
                    "name": "Primary",
                    "enabled": True,
                }
            ],
            "current_index": 0,
        }
        with self.Session() as session:
            save_secure_api_keys_payload(session, payload, actor_label="test-admin")
            session.commit()

        with self.Session() as session:
            loaded = load_secure_api_keys_payload(session)
            previews = list_secure_api_key_previews(session)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["keys"][0]["key"], "AIzaFakeKey1234567890")
            self.assertEqual(previews[0]["name"], "Primary")
            self.assertIn("...", previews[0]["preview"])


if __name__ == "__main__":
    unittest.main()
