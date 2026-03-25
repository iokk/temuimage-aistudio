#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from temu_core.billing import seed_default_workspace
from temu_core.db import session_scope


def main() -> None:
    with session_scope() as session:
        result = seed_default_workspace(session)
    print("Default workspace ready")
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
