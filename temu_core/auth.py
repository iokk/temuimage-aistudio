from __future__ import annotations

import base64
from datetime import datetime
import hashlib
import json
import os
import re
import secrets
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from .billing import ensure_default_organization
from .models import (
    AuditLog,
    OrganizationMember,
    PlatformConfig,
    Project,
    User,
    UserBackup,
    UsageEvent,
    WalletLedgerEntry,
)
from .settings import get_platform_settings
from .team import (
    ensure_organization_member,
    ensure_workspace_project,
    get_membership_for_user,
    get_workspace_context_for_user,
)


REGISTRATION_OPEN_KEY = "registration_open"
SYSTEM_API_KEYS_KEY = "system_api_keys_v1"
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260000


def normalize_username(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip().lower())
    clean = clean.strip("-._")
    return clean[:60]


def validate_username(value: str) -> str:
    username = normalize_username(value)
    if len(username) < 3:
        raise ValueError("用户名至少需要 3 个字符")
    return username


def _fernet_instance() -> Optional[Fernet]:
    secret = (get_platform_settings().encryption_key or "").strip()
    if not secret:
        return None
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encryption_available() -> bool:
    return _fernet_instance() is not None


def encrypt_text(value: str) -> str:
    fernet = _fernet_instance()
    if fernet is None:
        raise ValueError("PLATFORM_ENCRYPTION_KEY 未配置，无法加密保存敏感信息")
    return fernet.encrypt(str(value or "").encode("utf-8")).decode("utf-8")


def decrypt_text(value: str) -> str:
    fernet = _fernet_instance()
    if fernet is None:
        raise ValueError("PLATFORM_ENCRYPTION_KEY 未配置，无法解密敏感信息")
    try:
        return fernet.decrypt(str(value or "").encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("敏感配置无法解密，请检查 PLATFORM_ENCRYPTION_KEY") from exc


def hash_password(password: str, salt: str = "") -> str:
    raw_password = str(password or "")
    if len(raw_password) < 6:
        raise ValueError("密码至少需要 6 个字符")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        raw_password.encode("utf-8"),
        bytes.fromhex(salt),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, digest = str(encoded or "").split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        expected = hash_password(password, salt=salt)
        return secrets.compare_digest(expected, encoded)
    except Exception:
        return False


def mask_api_key(value: str) -> str:
    clean = str(value or "").strip()
    if len(clean) <= 10:
        return "***"
    return f"{clean[:6]}...{clean[-4:]}"


def _normalize_api_keys_payload(data) -> dict:
    payload = data if isinstance(data, dict) else {}
    keys = payload.get("keys", [])
    clean_keys = []
    for entry in keys if isinstance(keys, list) else []:
        if isinstance(entry, str):
            raw_key = entry.strip()
            if raw_key:
                clean_keys.append({"key": raw_key, "name": "Key", "enabled": True})
            continue
        if not isinstance(entry, dict):
            continue
        raw_key = str(entry.get("key") or "").strip()
        if not raw_key:
            continue
        clean_keys.append(
            {
                "key": raw_key,
                "name": str(entry.get("name") or "").strip() or "Key",
                "enabled": bool(entry.get("enabled", True)),
                "expires": str(entry.get("expires") or "").strip(),
            }
        )
    return {
        "keys": clean_keys,
        "current_index": int(payload.get("current_index", 0) or 0),
    }


def get_platform_config(session, config_key: str) -> Optional[PlatformConfig]:
    return session.scalar(
        select(PlatformConfig).where(PlatformConfig.config_key == config_key)
    )


def set_platform_json_config(
    session, config_key: str, value, actor_label: str = "system"
) -> PlatformConfig:
    config = get_platform_config(session, config_key)
    if config is None:
        config = PlatformConfig(config_key=config_key)
        session.add(config)
    config.config_value_json = value
    config.updated_by_label = actor_label
    session.flush()
    return config


def get_platform_json_config(session, config_key: str, default=None):
    config = get_platform_config(session, config_key)
    if config is None:
        return default
    return config.config_value_json if config.config_value_json is not None else default


def is_registration_open(session) -> bool:
    value = get_platform_json_config(session, REGISTRATION_OPEN_KEY, True)
    return bool(value)


def set_registration_open(session, enabled: bool, actor_label: str = "system") -> bool:
    set_platform_json_config(session, REGISTRATION_OPEN_KEY, bool(enabled), actor_label)
    session.add(
        AuditLog(
            organization_id=ensure_default_organization(session).id,
            actor_label=actor_label,
            action="set_registration_open",
            subject_type="platform_config",
            subject_id=REGISTRATION_OPEN_KEY,
            details_json={"enabled": bool(enabled)},
        )
    )
    session.flush()
    return bool(enabled)


def load_secure_api_keys_payload(session) -> Optional[dict]:
    config = get_platform_config(session, SYSTEM_API_KEYS_KEY)
    if config is None or not config.encrypted_value:
        return None
    decrypted = decrypt_text(config.encrypted_value)
    return _normalize_api_keys_payload(json.loads(decrypted or "{}"))


def save_secure_api_keys_payload(
    session, payload: dict, actor_label: str = "system"
) -> dict:
    clean_payload = _normalize_api_keys_payload(payload)
    config = get_platform_config(session, SYSTEM_API_KEYS_KEY)
    if config is None:
        config = PlatformConfig(config_key=SYSTEM_API_KEYS_KEY)
        session.add(config)
    config.encrypted_value = encrypt_text(json.dumps(clean_payload, ensure_ascii=False))
    config.config_value_json = {
        "current_index": clean_payload.get("current_index", 0),
        "keys": [
            {
                "name": entry.get("name", "Key"),
                "enabled": bool(entry.get("enabled", True)),
                "expires": entry.get("expires", ""),
                "preview": mask_api_key(entry.get("key", "")),
            }
            for entry in clean_payload.get("keys", [])
        ],
    }
    config.updated_by_label = actor_label
    session.add(
        AuditLog(
            organization_id=ensure_default_organization(session).id,
            actor_label=actor_label,
            action="save_system_api_keys",
            subject_type="platform_config",
            subject_id=SYSTEM_API_KEYS_KEY,
            details_json={"key_count": len(clean_payload.get("keys", []))},
        )
    )
    session.flush()
    return clean_payload


def list_secure_api_key_previews(session) -> list[dict]:
    config = get_platform_config(session, SYSTEM_API_KEYS_KEY)
    if config is None:
        return []
    value = (
        config.config_value_json if isinstance(config.config_value_json, dict) else {}
    )
    keys = value.get("keys", []) if isinstance(value, dict) else []
    return [entry for entry in keys if isinstance(entry, dict)]


def ensure_local_user(
    session,
    username: str,
    password: str,
    display_name: str = "",
    email: str = "",
    role: str = "member",
    actor_label: str = "self-service",
    allow_closed_registration: bool = False,
) -> User:
    if not allow_closed_registration and not is_registration_open(session):
        raise ValueError("当前已停止新用户注册")
    normalized_username = validate_username(username)
    existing = session.scalar(select(User).where(User.username == normalized_username))
    if existing is not None and existing.status != "deleted":
        raise ValueError("用户名已存在")
    if existing is None:
        user = User(
            username=normalized_username,
            display_name=str(display_name or normalized_username).strip()[:160],
            email=str(email or "").strip()[:255],
            auth_provider="local",
            password_hash=hash_password(password),
            status="active",
            deleted_at=None,
        )
        session.add(user)
        session.flush()
    else:
        user = existing
        user.display_name = str(
            display_name or existing.display_name or normalized_username
        ).strip()[:160]
        user.email = str(email or existing.email or "").strip()[:255]
        user.auth_provider = "local"
        user.password_hash = hash_password(password)
        user.status = "active"
        user.deleted_at = None
        session.flush()
    organization = ensure_default_organization(session)
    ensure_organization_member(session, organization, user, role=role)
    ensure_workspace_project(
        session,
        organization,
        name=get_platform_settings().default_project_name,
        actor_label=actor_label,
    )
    session.add(
        AuditLog(
            organization_id=organization.id,
            actor_label=actor_label,
            action="create_user",
            subject_type="user",
            subject_id=user.id,
            details_json={"username": user.username, "role": role},
        )
    )
    session.flush()
    return user


def authenticate_local_user(session, username: str, password: str) -> User:
    normalized_username = validate_username(username)
    user = session.scalar(select(User).where(User.username == normalized_username))
    if user is None or user.auth_provider != "local":
        raise ValueError("用户名或密码错误")
    if user.status != "active" or user.deleted_at is not None:
        raise ValueError("用户已被禁用或删除")
    if not verify_password(password, user.password_hash):
        raise ValueError("用户名或密码错误")
    organization = ensure_default_organization(session)
    membership = get_membership_for_user(session, organization.id, user.id)
    if membership is None or membership.status != "active":
        raise ValueError("当前账号未启用")
    user.last_login_at = datetime.utcnow()
    session.flush()
    return user


def list_registered_users(session) -> list[dict]:
    organization = ensure_default_organization(session)
    rows = session.execute(
        select(User, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(
            OrganizationMember.organization_id == organization.id,
            User.auth_provider == "local",
        )
        .order_by(User.created_at.asc())
    ).all()
    result = []
    for user, membership in rows:
        result.append(
            {
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "email": user.email,
                "role": membership.role,
                "status": user.status,
                "membership_status": membership.status,
                "created_at": user.created_at,
                "last_login_at": user.last_login_at,
                "deleted_at": user.deleted_at,
            }
        )
    return result


def set_local_user_status(
    session,
    user_id: str,
    status: str,
    actor_label: str,
    reason: str = "",
) -> User:
    user = session.scalar(
        select(User).where(User.id == user_id, User.auth_provider == "local")
    )
    if user is None:
        raise ValueError("用户不存在")
    organization = ensure_default_organization(session)
    membership = get_membership_for_user(session, organization.id, user.id)
    if membership is None:
        raise ValueError("成员关系不存在")
    normalized_status = str(status or "active").strip().lower()
    if normalized_status not in {"active", "disabled", "deleted"}:
        raise ValueError("不支持的用户状态")
    user.status = normalized_status
    membership.status = "active" if normalized_status == "active" else normalized_status
    if normalized_status == "deleted":
        user.deleted_at = datetime.utcnow()
        user.password_hash = ""
    elif normalized_status == "active":
        user.deleted_at = None
    session.add(
        AuditLog(
            organization_id=organization.id,
            actor_label=actor_label,
            action="set_user_status",
            subject_type="user",
            subject_id=user.id,
            details_json={"status": normalized_status, "reason": reason},
        )
    )
    session.flush()
    return user


def set_local_user_role(
    session, user_id: str, role: str, actor_label: str, reason: str = ""
) -> User:
    user = session.scalar(
        select(User).where(User.id == user_id, User.auth_provider == "local")
    )
    if user is None:
        raise ValueError("用户不存在")
    normalized_role = str(role or "member").strip().lower()
    if normalized_role not in {"member", "admin"}:
        raise ValueError("角色必须是 member 或 admin")
    organization = ensure_default_organization(session)
    membership = get_membership_for_user(session, organization.id, user.id)
    if membership is None:
        membership = ensure_organization_member(
            session, organization, user, role=normalized_role
        )
    membership.role = normalized_role
    session.add(
        AuditLog(
            organization_id=organization.id,
            actor_label=actor_label,
            action="set_user_role",
            subject_type="user",
            subject_id=user.id,
            details_json={"role": normalized_role, "reason": reason},
        )
    )
    session.flush()
    return user


def reset_local_user_password(
    session, user_id: str, new_password: str, actor_label: str
) -> User:
    user = session.scalar(
        select(User).where(User.id == user_id, User.auth_provider == "local")
    )
    if user is None:
        raise ValueError("用户不存在")
    user.password_hash = hash_password(new_password)
    if user.status == "deleted":
        user.status = "active"
        user.deleted_at = None
    session.add(
        AuditLog(
            organization_id=ensure_default_organization(session).id,
            actor_label=actor_label,
            action="reset_user_password",
            subject_type="user",
            subject_id=user.id,
            details_json={"username": user.username},
        )
    )
    session.flush()
    return user


def _serialize_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _serialize_user_snapshot(session, user: User) -> dict:
    organization = ensure_default_organization(session)
    memberships = (
        session.execute(
            select(OrganizationMember).where(OrganizationMember.user_id == user.id)
        )
        .scalars()
        .all()
    )
    usage_events = (
        session.execute(
            select(UsageEvent)
            .where(UsageEvent.user_id == user.id)
            .order_by(UsageEvent.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    ledger_entries = (
        session.execute(
            select(WalletLedgerEntry)
            .where(WalletLedgerEntry.user_id == user.id)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    projects = list(
        session.execute(
            select(Project).where(Project.organization_id == organization.id)
        ).scalars()
    )
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "auth_provider": user.auth_provider,
            "status": user.status,
            "created_at": _serialize_datetime(user.created_at),
            "updated_at": _serialize_datetime(user.updated_at),
            "last_login_at": _serialize_datetime(user.last_login_at),
            "deleted_at": _serialize_datetime(user.deleted_at),
        },
        "memberships": [
            {
                "id": item.id,
                "organization_id": item.organization_id,
                "user_id": item.user_id,
                "role": item.role,
                "status": item.status,
                "created_at": _serialize_datetime(item.created_at),
                "updated_at": _serialize_datetime(item.updated_at),
            }
            for item in memberships
        ],
        "usage_events": [
            {
                "id": item.id,
                "feature": item.feature,
                "provider": item.provider,
                "model": item.model,
                "charge_source": item.charge_source,
                "request_count": item.request_count,
                "output_images": item.output_images,
                "tokens_used": item.tokens_used,
                "created_at": _serialize_datetime(item.created_at),
            }
            for item in usage_events
        ],
        "wallet_ledger_entries": [
            {
                "id": item.id,
                "entry_type": item.entry_type,
                "amount_delta": item.amount_delta,
                "balance_after": item.balance_after,
                "reference_type": item.reference_type,
                "reference_id": item.reference_id,
                "note": item.note,
                "created_at": _serialize_datetime(item.created_at),
            }
            for item in ledger_entries
        ],
        "projects": [
            {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "created_at": _serialize_datetime(item.created_at),
            }
            for item in projects
        ],
    }


def backup_and_delete_local_user(
    session, user_id: str, actor_label: str, reason: str = ""
) -> UserBackup:
    user = session.scalar(
        select(User).where(User.id == user_id, User.auth_provider == "local")
    )
    if user is None:
        raise ValueError("用户不存在")
    snapshot = _serialize_user_snapshot(session, user)
    backup = UserBackup(
        original_user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        deleted_by_label=actor_label,
        reason=reason,
        snapshot_json=snapshot,
    )
    session.add(backup)
    set_local_user_status(
        session,
        user_id=user.id,
        status="deleted",
        actor_label=actor_label,
        reason=reason or "backup_and_delete",
    )
    session.add(
        AuditLog(
            organization_id=ensure_default_organization(session).id,
            actor_label=actor_label,
            action="backup_and_delete_user",
            subject_type="user_backup",
            subject_id=backup.id,
            details_json={"user_id": user.id, "username": user.username},
        )
    )
    session.flush()
    return backup


def list_user_backups(session) -> list[UserBackup]:
    return (
        session.execute(select(UserBackup).order_by(UserBackup.created_at.desc()))
        .scalars()
        .all()
    )


def get_login_context_for_user(session, user: User, project_id: str = ""):
    return get_workspace_context_for_user(session, user, project_id=project_id)
