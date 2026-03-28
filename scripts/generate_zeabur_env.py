#!/usr/bin/env python3
from __future__ import annotations

import argparse
import secrets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Zeabur-ready env template values"
    )
    parser.add_argument("--web-domain", default="studio.example.com")
    parser.add_argument("--api-domain", default="api.example.com")
    parser.add_argument("--casdoor-issuer", default="https://casdoor.example.com")
    parser.add_argument("--admin-emails", default="admin@example.com")
    parser.add_argument("--allowed-domains", default="example.com")
    parser.add_argument("--bootstrap-email", default="")
    parser.add_argument("--bootstrap-name", default="Platform Admin")
    args = parser.parse_args()

    nextauth_secret = secrets.token_urlsafe(48)
    system_encryption_key = secrets.token_urlsafe(48)
    bootstrap_password = secrets.token_urlsafe(24)
    bootstrap_email = args.bootstrap_email or args.admin_emails.split(",")[0].strip()

    print("# Zeabur template variables")
    print(f"WEB_DOMAIN={args.web_domain}")
    print(f"API_DOMAIN={args.api_domain}")
    print(f"NEXTAUTH_SECRET={nextauth_secret}")
    print(f"BOOTSTRAP_LOGIN_EMAIL={bootstrap_email}")
    print(f"BOOTSTRAP_LOGIN_PASSWORD={bootstrap_password}")
    print(f"BOOTSTRAP_LOGIN_NAME={args.bootstrap_name}")
    print("CASDOOR_ISSUER=")
    print("CASDOOR_CLIENT_ID=")
    print("CASDOOR_CLIENT_SECRET=")
    print(f"TEAM_ADMIN_EMAILS={args.admin_emails}")
    print(f"TEAM_ALLOWED_EMAIL_DOMAINS={args.allowed_domains}")
    print(f"SYSTEM_ENCRYPTION_KEY={system_encryption_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
