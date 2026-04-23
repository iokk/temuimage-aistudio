from datetime import datetime, timezone
import platform
import sqlite3
import ssl
import sys

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_db_connection

router = APIRouter()


@router.get("/health")
def get_health(
    request: Request,
    connection: sqlite3.Connection = Depends(get_db_connection),
) -> dict:
    runtime = request.app.state.runtime
    provider_count = connection.execute("SELECT COUNT(*) AS count FROM providers").fetchone()["count"]
    setting_count = connection.execute("SELECT COUNT(*) AS count FROM settings").fetchone()["count"]
    task_count = connection.execute("SELECT COUNT(*) AS count FROM tasks").fetchone()["count"]
    project_count = connection.execute("SELECT COUNT(*) AS count FROM projects").fetchone()["count"]
    return {
        "status": "ok",
        "service": "ecommerce-workbench-desktop-api",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python_version": sys.version.split()[0],
            "python_impl": platform.python_implementation(),
            "openssl": ssl.OPENSSL_VERSION,
        },
        "package": {
            "packaged": request.app.state.runtime.packaged,
            "resource_root": str(request.app.state.runtime.resource_root)
            if request.app.state.runtime.resource_root
            else "",
        },
        "paths": {
          "root": str(runtime.root_dir),
          "logs": str(runtime.log_dir),
          "cache": str(runtime.cache_dir),
          "files": str(runtime.files_dir),
          "db": str(runtime.db_path),
        },
        "stats": {
            "providers": provider_count,
            "settings": setting_count,
            "tasks": task_count,
            "projects": project_count,
        },
    }
