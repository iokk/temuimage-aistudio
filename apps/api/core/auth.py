from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from urllib.request import urlopen
from uuid import NAMESPACE_URL, uuid5

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.api.core.config import AppSettings, get_settings
from apps.api.job_repository import job_repository


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: str
    issuer: str
    subject: str
    email: str
    name: str
    email_verified: bool
    is_admin: bool
    is_team_member: bool


def _parse_csv(value: str | None) -> list[str]:
    return [item.strip().lower() for item in (value or "").split(",") if item.strip()]


def _build_user_id(issuer: str, subject: str) -> str:
    stable_uuid = uuid5(NAMESPACE_URL, f"{issuer}:{subject}")
    return f"user_{stable_uuid.hex}"


class CasdoorTokenVerifier:
    def __init__(self, settings: AppSettings):
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self._settings.casdoor_issuer
            and self._settings.casdoor_client_id
            and self._settings.casdoor_client_secret
        )

    @lru_cache(maxsize=1)
    def _get_jwks_client(self) -> jwt.PyJWKClient:
        issuer = self._settings.casdoor_issuer.rstrip("/")
        discovery_url = f"{issuer}/.well-known/openid-configuration"
        with urlopen(discovery_url, timeout=5) as response:
            discovery_document = json.load(response)

        jwks_uri = str(discovery_document["jwks_uri"])
        return jwt.PyJWKClient(jwks_uri)

    def verify(self, raw_token: str) -> dict:
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Casdoor is not configured",
            )

        jwks_client = self._get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(raw_token)
        audience = (
            self._settings.casdoor_api_audience
            or self._settings.casdoor_client_id
            or None
        )

        try:
            return jwt.decode(
                raw_token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "ES256"],
                audience=audience,
                issuer=self._settings.casdoor_issuer,
                options={"verify_aud": bool(audience)},
            )
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Casdoor token",
            ) from exc


@lru_cache(maxsize=1)
def get_token_verifier() -> CasdoorTokenVerifier:
    return CasdoorTokenVerifier(get_settings())


def _build_principal(claims: dict) -> Principal:
    issuer = str(claims.get("iss") or "").strip()
    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().lower()
    name = str(
        claims.get("name")
        or claims.get("preferred_username")
        or claims.get("nickname")
        or email
    ).strip()
    email_verified = bool(claims.get("email_verified"))

    if not issuer or not subject or not email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Casdoor token missing required identity claims",
        )

    team_admins = _parse_csv(os.getenv("TEAM_ADMIN_EMAILS"))
    team_domains = _parse_csv(os.getenv("TEAM_ALLOWED_EMAIL_DOMAINS"))
    email_domain = email.split("@")[-1] if "@" in email else ""
    is_admin = email in team_admins
    is_team_member = is_admin or (
        email_domain in team_domains if email_domain else False
    )
    user_id = _build_user_id(issuer, subject)

    job_repository.upsert_user(
        user_id=user_id,
        email=email,
        name=name,
        issuer=issuer,
        subject=subject,
        email_verified=email_verified,
        last_login_at=datetime.now(timezone.utc),
    )

    return Principal(
        user_id=user_id,
        issuer=issuer,
        subject=subject,
        email=email,
        name=name,
        email_verified=email_verified,
        is_admin=is_admin,
        is_team_member=is_team_member,
    )


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    claims = get_token_verifier().verify(credentials.credentials)
    return _build_principal(claims)


def require_team_member(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    if not principal.is_team_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team membership required",
        )
    return principal


def require_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return principal
