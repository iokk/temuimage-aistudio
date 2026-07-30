#!/usr/bin/env python3
"""Run secret-safe acceptance checks against a saved TuLite provider."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
from provider_acceptance import verify_provider  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify a saved provider without printing its API key."
    )
    parser.add_argument("--provider-id", default="")
    parser.add_argument("--skip-responses", action="store_true")
    parser.add_argument("--live-image", action="store_true")
    parser.add_argument("--image-output", type=Path)
    args = parser.parse_args(argv)
    if args.live_image and args.image_output is None:
        parser.error("--live-image requires --image-output")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    provider = (
        app.get_provider_by_id(args.provider_id)
        if args.provider_id
        else app.get_active_provider()
    )
    if not provider:
        print(
            json.dumps(
                {"ok": False, "error": "未找到可验收的提供商"},
                ensure_ascii=False,
            )
        )
        return 2

    report = verify_provider(
        provider,
        app,
        include_responses=not args.skip_responses,
        include_live_image=args.live_image,
        image_output=args.image_output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
