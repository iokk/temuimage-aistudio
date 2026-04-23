import atexit
import os
import sys
import webbrowser
from pathlib import Path

from .config_bridge import bridge_runtime_manifest, bridge_settings
from .migrate import migrate_existing_local_data
from .paths import get_desktop_paths
from .runtime import (
    acquire_single_instance_lock,
    find_available_port,
    release_single_instance_lock,
    start_backend,
    stop_backend,
    wait_for_health,
)
from .window import open_desktop_window, pywebview_available


def open_browser(port: int):
    webbrowser.open(f"http://127.0.0.1:{port}")


def _append_launcher_log(log_path: str, message: str):
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(message.rstrip() + "\n")
    except Exception:
        return


def open_ui_for_port(port: int, log_path: str, prefer_desktop_window: bool = True) -> str:
    url = f"http://127.0.0.1:{port}"
    if prefer_desktop_window and pywebview_available():
        if open_desktop_window(url):
            _append_launcher_log(log_path, f"ui_mode=desktop-window url={url}")
            return "desktop-window"
        _append_launcher_log(log_path, f"ui_fallback=browser reason=pywebview-failed url={url}")
    open_browser(port)
    _append_launcher_log(log_path, f"ui_mode=browser url={url}")
    return "browser"


def run_launcher(open_ui=True, prefer_desktop_window=True):
    app_path = Path(__file__).resolve().parent.parent / "app.py"
    if not app_path.exists():
        raise FileNotFoundError(f"未找到应用入口: {app_path}")
    paths = get_desktop_paths().ensure()
    paths.write_manifest()
    migrate_existing_local_data(paths)
    bridge_settings(paths)
    bridge_runtime_manifest(paths)
    lock_path = acquire_single_instance_lock()
    process = None

    def _cleanup():
        stop_backend(process)
        release_single_instance_lock(lock_path)

    atexit.register(_cleanup)

    port = find_available_port(8501)
    process, log_path = start_backend(app_path, port)
    if not wait_for_health(port, timeout_seconds=60):
        stop_backend(process)
        raise RuntimeError(f"本地服务启动失败，请检查日志: {log_path}")
    ui_mode = "none"
    if open_ui:
        ui_mode = open_ui_for_port(
            port, str(log_path), prefer_desktop_window=prefer_desktop_window
        )
    return {
        "port": port,
        "log_path": str(log_path),
        "process": process,
        "ui_mode": ui_mode,
        "lock_path": str(lock_path),
        "cleanup": _cleanup,
    }


def close_launcher(result: dict):
    cleanup = (result or {}).get("cleanup")
    if callable(cleanup):
        cleanup()
        return
    process = (result or {}).get("process")
    if process:
        stop_backend(process)
    lock_path = (result or {}).get("lock_path")
    if lock_path:
        release_single_instance_lock(Path(lock_path))


def main():
    prefer_desktop_window = (
        os.getenv("ECOMMERCE_WORKBENCH_PREFER_DESKTOP_WINDOW", "1").strip()
        not in {"0", "false", "False"}
    )
    result = run_launcher(open_ui=True, prefer_desktop_window=prefer_desktop_window)
    print(f"桌面启动器已启动，本地地址: http://127.0.0.1:{result['port']}")
    print(f"日志文件: {result['log_path']}")
    print(f"界面模式: {result['ui_mode']}")
    if result["ui_mode"] == "browser":
        try:
            result["process"].wait()
        except KeyboardInterrupt:
            close_launcher(result)
    else:
        close_launcher(result)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"启动失败: {exc}", file=sys.stderr)
        sys.exit(1)
