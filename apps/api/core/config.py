from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppSettings:
    app_name: str
    app_version: str
    database_url: str
    redis_url: str
    auto_bootstrap_db: bool
    casdoor_issuer: str
    casdoor_client_id: str
    casdoor_client_secret: str
    casdoor_api_audience: str


def get_settings() -> AppSettings:
    return AppSettings(
        app_name=os.getenv("API_APP_NAME", "XiaoBaiTu API"),
        app_version=os.getenv("API_APP_VERSION", "1.0.0"),
        database_url=os.getenv("DATABASE_URL", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        auto_bootstrap_db=os.getenv("AUTO_BOOTSTRAP_DB", "false").lower() == "true",
        casdoor_issuer=os.getenv("CASDOOR_ISSUER", "").strip(),
        casdoor_client_id=os.getenv("CASDOOR_CLIENT_ID", "").strip(),
        casdoor_client_secret=os.getenv("CASDOOR_CLIENT_SECRET", "").strip(),
        casdoor_api_audience=os.getenv("CASDOOR_API_AUDIENCE", "").strip(),
    )
