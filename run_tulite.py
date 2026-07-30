"""Start TuLite's background task supervisor before the Streamlit server."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    import app

    app.apply_proxy_settings()
    app.ensure_task_supervisor()
    os.environ["TULITE_BOOTSTRAP_SUPERVISOR"] = "1"

    from streamlit.web import cli as streamlit_cli

    app_path = Path(__file__).resolve().with_name("app.py")
    streamlit_args = sys.argv[1:]
    sys.argv = ["streamlit", "run", str(app_path), *streamlit_args]
    return int(streamlit_cli.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
