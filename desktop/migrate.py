import json
import shutil
from datetime import datetime
from pathlib import Path

from .config_bridge import bridge_runtime_manifest, bridge_settings
from .paths import DesktopPaths, get_desktop_paths
from snapshots.create_snapshot import create_snapshot


MIGRATION_STATE = "migration-state.json"
MIGRATION_VERSION = 1


def _repo_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def _migration_state_path(paths: DesktopPaths) -> Path:
    return paths.runtime_root / MIGRATION_STATE


def _load_state(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_tree_if_exists(src: Path, dest: Path):
    if not src.exists():
        return False
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return True


def migrate_existing_local_data(paths: DesktopPaths = None):
    paths = paths or get_desktop_paths().ensure()
    state_path = _migration_state_path(paths)
    state = _load_state(state_path)
    if state.get("version") == MIGRATION_VERSION:
        bridge_settings(paths)
        bridge_runtime_manifest(paths)
        return {"migrated": False, "reason": "already-migrated"}

    repo_data = _repo_data_dir()
    snapshot_dir = create_snapshot("runnable", dry_run=False)
    copied = []
    try:
        paths.ensure()
        for name in ["settings.json", "providers.json", "history.json", "prompts.json", "compliance.json", "templates.json", "title_templates.json"]:
            if _copy_tree_if_exists(repo_data / name, paths.data_dir / name):
                copied.append(name)
        for name in ["task_uploads", "task_results"]:
            if _copy_tree_if_exists(repo_data / name, paths.data_dir / name):
                copied.append(name)
        if _copy_tree_if_exists(repo_data / "history", paths.projects_dir / "history"):
            copied.append("history")
        bridge_settings(paths)
        bridge_runtime_manifest(paths)
        _save_state(
            state_path,
            {
                "version": MIGRATION_VERSION,
                "migrated_at": datetime.now().isoformat(),
                "snapshot_dir": str(snapshot_dir),
                "copied": copied,
            },
        )
        return {"migrated": True, "snapshot_dir": str(snapshot_dir), "copied": copied}
    except Exception as exc:
        _save_state(
            state_path,
            {
                "version": 0,
                "failed_at": datetime.now().isoformat(),
                "snapshot_dir": str(snapshot_dir),
                "error": str(exc),
            },
        )
        raise RuntimeError(f"桌面数据迁移失败，已保留快照: {snapshot_dir}；错误: {exc}")
