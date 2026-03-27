from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    app_version: str
    database_url: str
    redis_url: str


def get_settings() -> AppSettings:
    return AppSettings(
        app_name=os.getenv("API_APP_NAME", "XiaoBaiTu API"),
        app_version=os.getenv("API_APP_VERSION", "0.1.0"),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    )
