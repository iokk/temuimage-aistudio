#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets


def build_template_variables(args: argparse.Namespace) -> list[tuple[str, str]]:
    nextauth_secret = args.nextauth_secret or secrets.token_urlsafe(48)
    system_encryption_key = args.system_encryption_key or secrets.token_urlsafe(48)
    return [
        ("WEB_DOMAIN", args.web_domain),
        ("API_DOMAIN", args.api_domain),
        ("NEXTAUTH_SECRET", nextauth_secret),
        ("CASDOOR_ISSUER", args.casdoor_issuer),
        ("CASDOOR_CLIENT_ID", args.casdoor_client_id),
        ("CASDOOR_CLIENT_SECRET", args.casdoor_client_secret),
        ("CASDOOR_API_AUDIENCE", args.casdoor_api_audience),
        ("TEAM_ADMIN_EMAILS", args.admin_emails),
        ("TEAM_ALLOWED_EMAIL_DOMAINS", args.allowed_domains),
        ("SYSTEM_ENCRYPTION_KEY", system_encryption_key),
    ]


def build_service_env_blocks(
    template_variables: dict[str, str],
) -> dict[str, list[tuple[str, str]]]:
    web_domain = template_variables["WEB_DOMAIN"]
    api_domain = template_variables["API_DOMAIN"]
    return {
        "web": [
            ("NEXT_PUBLIC_API_BASE_URL", f"https://{api_domain}"),
            ("NEXTAUTH_URL", f"https://{web_domain}"),
            ("NEXTAUTH_SECRET", template_variables["NEXTAUTH_SECRET"]),
            ("CASDOOR_ISSUER", template_variables["CASDOOR_ISSUER"]),
            ("CASDOOR_CLIENT_ID", template_variables["CASDOOR_CLIENT_ID"]),
            ("CASDOOR_CLIENT_SECRET", template_variables["CASDOOR_CLIENT_SECRET"]),
            ("TEAM_ADMIN_EMAILS", template_variables["TEAM_ADMIN_EMAILS"]),
            (
                "TEAM_ALLOWED_EMAIL_DOMAINS",
                template_variables["TEAM_ALLOWED_EMAIL_DOMAINS"],
            ),
        ],
        "api": [
            ("DATABASE_URL", "${POSTGRES_CONNECTION_STRING}"),
            ("REDIS_URL", "${REDIS_CONNECTION_STRING}"),
            ("JOB_STORE_BACKEND", "database"),
            ("ASYNC_JOB_BACKEND", "celery"),
            ("AUTO_BOOTSTRAP_DB", "true"),
            ("API_APP_NAME", "XiaoBaiTu API"),
            ("API_APP_VERSION", "1.0.0"),
            ("SYSTEM_ENCRYPTION_KEY", template_variables["SYSTEM_ENCRYPTION_KEY"]),
            ("CASDOOR_ISSUER", template_variables["CASDOOR_ISSUER"]),
            ("CASDOOR_CLIENT_ID", template_variables["CASDOOR_CLIENT_ID"]),
            ("CASDOOR_CLIENT_SECRET", template_variables["CASDOOR_CLIENT_SECRET"]),
            ("CASDOOR_API_AUDIENCE", template_variables["CASDOOR_API_AUDIENCE"]),
            ("TEAM_ADMIN_EMAILS", template_variables["TEAM_ADMIN_EMAILS"]),
            (
                "TEAM_ALLOWED_EMAIL_DOMAINS",
                template_variables["TEAM_ALLOWED_EMAIL_DOMAINS"],
            ),
        ],
        "worker": [
            ("DATABASE_URL", "${POSTGRES_CONNECTION_STRING}"),
            ("REDIS_URL", "${REDIS_CONNECTION_STRING}"),
            ("JOB_STORE_BACKEND", "database"),
            ("ASYNC_JOB_BACKEND", "celery"),
            ("AUTO_BOOTSTRAP_DB", "false"),
            ("SYSTEM_ENCRYPTION_KEY", template_variables["SYSTEM_ENCRYPTION_KEY"]),
            ("CASDOOR_ISSUER", template_variables["CASDOOR_ISSUER"]),
            ("CASDOOR_CLIENT_ID", template_variables["CASDOOR_CLIENT_ID"]),
            ("CASDOOR_CLIENT_SECRET", template_variables["CASDOOR_CLIENT_SECRET"]),
            ("CASDOOR_API_AUDIENCE", template_variables["CASDOOR_API_AUDIENCE"]),
            ("TEAM_ADMIN_EMAILS", template_variables["TEAM_ADMIN_EMAILS"]),
            (
                "TEAM_ALLOWED_EMAIL_DOMAINS",
                template_variables["TEAM_ALLOWED_EMAIL_DOMAINS"],
            ),
        ],
    }


def format_env_block(title: str, values: list[tuple[str, str]]) -> str:
    lines = [title]
    lines.extend(f"{key}={value}" for key, value in values)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Zeabur-ready env template values"
    )
    parser.add_argument("--web-domain", default="studio.example.com")
    parser.add_argument("--api-domain", default="api.example.com")
    parser.add_argument("--casdoor-issuer", default="https://casdoor.example.com")
    parser.add_argument("--casdoor-client-id", default="replace-with-casdoor-client-id")
    parser.add_argument(
        "--casdoor-client-secret", default="replace-with-casdoor-client-secret"
    )
    parser.add_argument("--casdoor-api-audience", default="")
    parser.add_argument("--admin-emails", default="admin@example.com")
    parser.add_argument("--allowed-domains", default="example.com")
    parser.add_argument(
        "--format",
        choices=["template", "services", "all"],
        default="all",
        help="Output template variables only, per-service env blocks only, or both.",
    )
    parser.add_argument("--nextauth-secret", default="")
    parser.add_argument("--system-encryption-key", default="")
    args = parser.parse_args()

    template_variables = build_template_variables(args)
    template_map = dict(template_variables)
    outputs: list[str] = []

    if args.format in {"template", "all"}:
        outputs.append(
            format_env_block("# Zeabur template variables", template_variables)
        )

    if args.format in {"services", "all"}:
        outputs.append(
            "\n".join(
                [
                    "# Service env blocks (for manual verification or raw Git fallback)",
                    format_env_block(
                        "[web]", build_service_env_blocks(template_map)["web"]
                    ),
                    format_env_block(
                        "[api]", build_service_env_blocks(template_map)["api"]
                    ),
                    format_env_block(
                        "[worker]", build_service_env_blocks(template_map)["worker"]
                    ),
                ]
            )
        )

    print("\n\n".join(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
