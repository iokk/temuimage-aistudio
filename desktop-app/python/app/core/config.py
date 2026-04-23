from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_env: str
    packaged: bool
    resource_root: Path | None
    api_host: str
    api_port: int
    app_data_dir: Path
    log_dir: Path
    cache_dir: Path
    files_dir: Path
    db_path: Path


def get_settings() -> Settings:
    app_data_dir = Path(
        os.getenv("ECOMMERCE_WORKBENCH_APP_DATA_DIR", Path.cwd() / ".runtime")
    )
    log_dir = Path(os.getenv("ECOMMERCE_WORKBENCH_LOG_DIR", app_data_dir / "logs"))
    cache_dir = Path(os.getenv("ECOMMERCE_WORKBENCH_CACHE_DIR", app_data_dir / "cache"))
    files_dir = Path(os.getenv("ECOMMERCE_WORKBENCH_FILES_DIR", app_data_dir / "files"))
    db_path = Path(os.getenv("ECOMMERCE_WORKBENCH_DB_PATH", app_data_dir / "app.db"))

    return Settings(
        app_env=os.getenv("ECOMMERCE_WORKBENCH_APP_ENV", "desktop"),
        packaged=os.getenv("ECOMMERCE_WORKBENCH_PACKAGED", "0") == "1",
        resource_root=Path(os.getenv("ECOMMERCE_WORKBENCH_RESOURCE_ROOT"))
        if os.getenv("ECOMMERCE_WORKBENCH_RESOURCE_ROOT")
        else None,
        api_host=os.getenv("ECOMMERCE_WORKBENCH_API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("ECOMMERCE_WORKBENCH_API_PORT", "8765")),
        app_data_dir=app_data_dir,
        log_dir=log_dir,
        cache_dir=cache_dir,
        files_dir=files_dir,
        db_path=db_path,
    )
