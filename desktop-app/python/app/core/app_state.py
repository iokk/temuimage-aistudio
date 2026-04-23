from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.db.bootstrap import initialize_database


@dataclass(frozen=True)
class RuntimeState:
    root_dir: Path
    log_dir: Path
    cache_dir: Path
    files_dir: Path
    db_path: Path
    log_file: Path
    packaged: bool
    resource_root: Path | None


def bootstrap_runtime_state(settings: Settings) -> RuntimeState:
    for directory in [
        settings.app_data_dir,
        settings.log_dir,
        settings.cache_dir,
        settings.files_dir,
        settings.files_dir / "projects",
        settings.files_dir / "temp",
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    settings.db_path.touch(exist_ok=True)
    log_file = settings.log_dir / "python-api.log"
    log_file.touch(exist_ok=True)
    initialize_database(settings.db_path)

    return RuntimeState(
        root_dir=settings.app_data_dir,
        log_dir=settings.log_dir,
        cache_dir=settings.cache_dir,
        files_dir=settings.files_dir,
        db_path=settings.db_path,
        log_file=log_file,
        packaged=settings.packaged,
        resource_root=settings.resource_root,
    )
