from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apps.api.db.base import Base
from apps.api.db.models import User


SYSTEM_USER_ID = "system"
SYSTEM_USER_EMAIL = "system@xiaobaitu.local"


def bootstrap_database(database_url: str) -> None:
    if not database_url:
        return

    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        row = session.get(User, SYSTEM_USER_ID)
        if not row:
            session.add(
                User(
                    id=SYSTEM_USER_ID,
                    email=SYSTEM_USER_EMAIL,
                    name="System",
                    mode="personal",
                    issuer="internal",
                    subject="system",
                    email_verified=True,
                )
            )
            session.commit()
