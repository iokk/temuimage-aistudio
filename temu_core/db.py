from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import database_enabled, get_platform_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    settings = get_platform_settings()
    if not settings.database_url:
        return None
    kwargs = {
        "future": True,
        "pool_pre_ping": True,
    }
    if settings.database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(settings.database_url, **kwargs)


@lru_cache(maxsize=1)
def get_session_factory():
    engine = get_engine()
    if engine is None:
        return None
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False,
    )


@contextmanager
def session_scope():
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("DATABASE_URL is not configured")
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_database_status(expected_tables: list[str] | None = None) -> dict:
    status = {
        "configured": database_enabled(),
        "reachable": False,
        "dialect": "",
        "missing_tables": [],
        "table_count": 0,
        "error": "",
    }
    if not status["configured"]:
        return status
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        status["reachable"] = True
        status["dialect"] = engine.dialect.name
        status["table_count"] = len(table_names)
        if expected_tables:
            status["missing_tables"] = [
                name for name in expected_tables if name not in table_names
            ]
    except Exception as exc:
        status["error"] = str(exc)
    return status
