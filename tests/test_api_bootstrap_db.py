from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

create_engine = None
Session = None
SYSTEM_USER_EMAIL = None
SYSTEM_USER_ID = None
bootstrap_database = None
User = None

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from apps.api.bootstrap_db import (
        SYSTEM_USER_EMAIL,
        SYSTEM_USER_ID,
        bootstrap_database,
    )
    from apps.api.db.models import User

    SQLALCHEMY_TESTS_AVAILABLE = True
except ModuleNotFoundError:
    SQLALCHEMY_TESTS_AVAILABLE = False


@unittest.skipUnless(SQLALCHEMY_TESTS_AVAILABLE, "sqlalchemy unavailable")
class BootstrapDatabaseTest(unittest.TestCase):
    def test_bootstrap_creates_system_user_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_url = f"sqlite+pysqlite:///{Path(temp_dir) / 'bootstrap.db'}"

            assert bootstrap_database is not None
            bootstrap_database(database_url)
            bootstrap_database(database_url)

            assert create_engine is not None
            assert Session is not None
            assert User is not None
            assert SYSTEM_USER_ID is not None
            assert SYSTEM_USER_EMAIL is not None
            engine = create_engine(database_url, future=True)
            with Session(engine) as session:
                system_user = session.get(User, SYSTEM_USER_ID)
                self.assertIsNotNone(system_user)
                assert system_user is not None
                self.assertEqual(system_user.email, SYSTEM_USER_EMAIL)
                self.assertEqual(system_user.mode, "personal")
                self.assertEqual(session.query(User).count(), 1)


if __name__ == "__main__":
    unittest.main()
