import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path


APP_SLUG = "ecommerce-image-workbench"
APP_NAME = "电商出图工作台"


def _home() -> Path:
    return Path.home()


def _platform_system() -> str:
    return platform.system().lower()


def _default_runtime_root() -> Path:
    explicit = os.getenv("ECOMMERCE_WORKBENCH_RUNTIME_ROOT", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    system = _platform_system()
    if system == "darwin":
        return _home() / "Library" / "Application Support" / APP_NAME
    if system == "windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / APP_NAME
    return _home() / ".local" / "share" / APP_SLUG


@dataclass
class DesktopPaths:
    runtime_root: Path
    config_dir: Path
    projects_dir: Path
    logs_dir: Path
    cache_dir: Path
    backups_dir: Path
    data_dir: Path
    files_dir: Path
    history_dir: Path

    def ensure(self):
        for path in [
            self.runtime_root,
            self.config_dir,
            self.projects_dir,
            self.logs_dir,
            self.cache_dir,
            self.backups_dir,
            self.data_dir,
            self.files_dir,
            self.history_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
        return self

    def as_env(self, port: int = 8501) -> dict:
        return {
            "ECOMMERCE_WORKBENCH_MODE": "desktop",
            "ECOMMERCE_WORKBENCH_RUNTIME_ROOT": str(self.runtime_root),
            "ECOMMERCE_WORKBENCH_DATA_DIR": str(self.data_dir),
            "ECOMMERCE_WORKBENCH_PROJECTS_DIR": str(self.projects_dir),
            "FILE_STORAGE_PATH": str(self.files_dir),
            "ECOMMERCE_WORKBENCH_LOG_DIR": str(self.logs_dir),
            "ECOMMERCE_WORKBENCH_CACHE_DIR": str(self.cache_dir),
            "ECOMMERCE_WORKBENCH_BACKUP_DIR": str(self.backups_dir),
            "APP_PORT": str(port),
        }

    def write_manifest(self):
        manifest = self.runtime_root / "runtime-paths.json"
        manifest.write_text(
            json.dumps(
                {
                    "runtime_root": str(self.runtime_root),
                    "config_dir": str(self.config_dir),
                    "projects_dir": str(self.projects_dir),
                    "logs_dir": str(self.logs_dir),
                    "cache_dir": str(self.cache_dir),
                    "backups_dir": str(self.backups_dir),
                    "data_dir": str(self.data_dir),
                    "files_dir": str(self.files_dir),
                    "history_dir": str(self.history_dir),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return manifest


def get_desktop_paths() -> DesktopPaths:
    root = _default_runtime_root()
    return DesktopPaths(
        runtime_root=root,
        config_dir=root / "config",
        projects_dir=root / "projects",
        logs_dir=root / "logs",
        cache_dir=root / "cache",
        backups_dir=root / "backups",
        data_dir=root / "config" / "data",
        files_dir=root / "cache" / "files",
        history_dir=root / "projects" / "history",
    )
