#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_json(url: str, bearer_token: str | None = None) -> dict:
    request = Request(url)
    if bearer_token:
        request.add_header("Authorization", f"Bearer {bearer_token}")

    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild V1 release smoke checks")
    parser.add_argument(
        "--api-base", required=True, help="API base URL, e.g. http://localhost:8000"
    )
    parser.add_argument("--web-base", help="Web base URL, e.g. http://localhost:3000")
    parser.add_argument(
        "--require-ready", action="store_true", help="Fail if readiness is not ready"
    )
    parser.add_argument(
        "--api-bearer-token",
        help="Admin Casdoor bearer token used for protected API checks",
    )
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    web_base = args.web_base.rstrip("/") if args.web_base else ""
    bearer_token = (args.api_bearer_token or "").strip() or None

    checks = []
    try:
        health = fetch_json(f"{api_base}/health")
        checks.append(("api-health", health.get("status") == "ok", health))

        if args.require_ready and not bearer_token:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "--require-ready requires --api-bearer-token",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1

        if bearer_token:
            runtime = fetch_json(f"{api_base}/v1/system/runtime", bearer_token)
            checks.append(
                (
                    "api-runtime",
                    runtime.get("auth_provider") == "Casdoor",
                    runtime,
                )
            )

            readiness = fetch_json(f"{api_base}/v1/system/readiness", bearer_token)
            ready = readiness.get("status") == "ready"
            checks.append(("api-readiness", ready or not args.require_ready, readiness))

            jobs_meta = fetch_json(f"{api_base}/v1/jobs/meta", bearer_token)
            checks.append(("jobs-meta", "task_types" in jobs_meta, jobs_meta))
        else:
            checks.append(
                (
                    "protected-checks-skipped",
                    True,
                    {"reason": "no api bearer token provided"},
                )
            )

        if web_base:
            with urlopen(f"{web_base}/login", timeout=15) as response:
                body = response.read().decode("utf-8")
                checks.append(
                    (
                        "web-login",
                        response.status == 200 and "Casdoor" in body,
                        {"status": response.status},
                    )
                )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2)
        )
        return 1

    ok = all(item[1] for item in checks)
    output = {
        "ok": ok,
        "checks": [
            {"name": name, "ok": passed, "details": details}
            for name, passed, details in checks
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
