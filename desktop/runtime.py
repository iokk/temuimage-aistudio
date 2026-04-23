import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .paths import get_desktop_paths


LOCK_FILE = "launcher.lock"


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def find_available_port(preferred: int = 8501, attempts: int = 20) -> int:
    for port in range(preferred, preferred + attempts):
        if not port_in_use(port):
            return port
    raise RuntimeError("没有可用端口")


def wait_for_health(port: int, timeout_seconds: int = 60) -> bool:
    deadline = time.time() + timeout_seconds
    url = f"http://127.0.0.1:{port}/_stcore/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.read().decode("utf-8", "ignore").strip() == "ok":
                    return True
        except Exception:
            time.sleep(1)
    return False


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_single_instance_lock() -> Path:
    paths = get_desktop_paths().ensure()
    lock_path = paths.runtime_root / LOCK_FILE
    if lock_path.exists():
        try:
            lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            existing_pid = int(lock_data.get("pid", 0))
            if _pid_exists(existing_pid):
                raise RuntimeError("应用已在运行中")
        except RuntimeError:
            raise
        except Exception:
            pass
    lock_path.write_text(
        json.dumps({"pid": os.getpid(), "started_at": time.time()}, indent=2),
        encoding="utf-8",
    )
    return lock_path


def release_single_instance_lock(lock_path: Path):
    try:
        if lock_path and lock_path.exists():
            lock_path.unlink()
    except Exception:
        return


def _python_executable() -> str:
    current = Path(sys.executable)
    if current.exists() and "venv" in current.as_posix():
        return str(current)
    project_root = Path(__file__).resolve().parent.parent
    candidates = [
        project_root / ".venv" / "bin" / "python",
        project_root / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(current)


def streamlit_command(app_path: Path, port: int) -> list:
    return [
        _python_executable(),
        "-m",
        "streamlit",
        "run",
        str(app_path),
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]


def start_backend(app_path: Path, port: int) -> tuple:
    paths = get_desktop_paths().ensure()
    log_path = paths.logs_dir / f"launcher-{int(time.time())}.log"
    env = os.environ.copy()
    env.update(paths.as_env(port=port))
    env.setdefault("PYTHONUNBUFFERED", "1")
    with open(log_path, "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            streamlit_command(app_path, port),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(app_path.parent),
            env=env,
        )
    return process, log_path


def stop_backend(process: subprocess.Popen):
    if not process:
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
