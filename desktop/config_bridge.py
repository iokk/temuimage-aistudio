import json
from pathlib import Path

from .paths import DesktopPaths


def _load_json(path: Path, default=None):
    if default is None:
        default = {}
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default.copy() if isinstance(default, dict) else default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def bridge_settings(paths: DesktopPaths) -> Path:
    settings_path = paths.data_dir / "settings.json"
    settings = _load_json(settings_path, {})
    if not settings.get("project_output_dir"):
        settings["project_output_dir"] = str(paths.projects_dir)
    if not settings.get("file_storage_path") or settings.get("file_storage_path") == "/app/data/files":
        settings["file_storage_path"] = str(paths.files_dir)
    settings.setdefault("file_storage_type", "local")
    _save_json(settings_path, settings)
    return settings_path


def bridge_runtime_manifest(paths: DesktopPaths) -> Path:
    manifest_path = paths.runtime_root / "desktop-config.json"
    manifest_path.write_text(
        json.dumps(
            {
                "data_dir": str(paths.data_dir),
                "projects_dir": str(paths.projects_dir),
                "logs_dir": str(paths.logs_dir),
                "cache_dir": str(paths.cache_dir),
                "backups_dir": str(paths.backups_dir),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path
