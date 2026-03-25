from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import secrets
import string

from sqlalchemy import func, select

from .models import (
    AdminTopUp,
    AuditLog,
    Organization,
    RedeemCode,
    RedeemCodeBatch,
    RedeemCodeRedemption,
    WalletAccount,
    WalletLedgerEntry,
)
from .settings import get_platform_settings


ALPHABET = string.ascii_uppercase + string.digits


def slugify_name(value: str) -> str:
    base = "".join(
        ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()
    )
    base = "-".join(part for part in base.split("-") if part)
    return base[:80] or f"org-{secrets.token_hex(4)}"


def hash_redeem_code(code: str) -> str:
    normalized = normalize_redeem_code(code)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_redeem_code(code: str) -> str:
    return "".join(ch for ch in str(code or "").upper() if ch.isalnum())


def preview_redeem_code(code: str) -> str:
    normalized = normalize_redeem_code(code)
    if len(normalized) <= 8:
        return normalized
    return f"{normalized[:4]}...{normalized[-4:]}"


def generate_redeem_code(
    prefix: str = "TEMU", body_groups: int = 3, group_size: int = 4
) -> str:
    clean_prefix = (
        "".join(ch for ch in str(prefix or "TEMU").upper() if ch.isalnum())[:8]
        or "TEMU"
    )
    groups = [
        "".join(secrets.choice(ALPHABET) for _ in range(group_size))
        for _ in range(body_groups)
    ]
    return "-".join([clean_prefix, *groups])


def ensure_default_organization(session):
    settings = get_platform_settings()
    org = session.scalar(
        select(Organization).where(
            Organization.slug == slugify_name(settings.default_org_name)
        )
    )
    if org is None:
        org = Organization(
            name=settings.default_org_name, slug=slugify_name(settings.default_org_name)
        )
        session.add(org)
        session.flush()
    return org


def get_or_create_org_wallet(session, organization: Organization) -> WalletAccount:
    wallet = session.scalar(
        select(WalletAccount).where(
            WalletAccount.owner_type == "organization",
            WalletAccount.owner_id == organization.id,
        )
    )
    if wallet is None:
        wallet = WalletAccount(
            owner_type="organization",
            owner_id=organization.id,
            name=f"{organization.name} Wallet",
            unit="credits",
        )
        session.add(wallet)
        session.flush()
    return wallet


def seed_default_workspace(session) -> dict:
    org = ensure_default_organization(session)
    wallet = get_or_create_org_wallet(session, org)
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        "wallet_id": wallet.id,
        "wallet_balance": wallet.cached_balance,
    }


def _append_ledger_entry(
    session,
    wallet: WalletAccount,
    organization: Organization,
    amount_delta: int,
    entry_type: str,
    actor_label: str,
    note: str,
    reference_type: str,
    reference_id: str,
    idempotency_key: str,
    metadata_json=None,
):
    existing = session.scalar(
        select(WalletLedgerEntry).where(
            WalletLedgerEntry.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing
    wallet.cached_balance = int(wallet.cached_balance or 0) + int(amount_delta)
    wallet.version = int(wallet.version or 1) + 1
    entry = WalletLedgerEntry(
        wallet_account_id=wallet.id,
        organization_id=organization.id,
        entry_type=entry_type,
        amount_delta=int(amount_delta),
        balance_after=int(wallet.cached_balance),
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        actor_label=actor_label,
        note=note,
        metadata_json=metadata_json,
    )
    session.add(entry)
    session.flush()
    return entry


def create_admin_adjustment(
    session,
    amount: int,
    operator_label: str,
    reason: str,
    adjustment_type: str = "admin_topup",
) -> dict:
    organization = ensure_default_organization(session)
    wallet = get_or_create_org_wallet(session, organization)
    amount = int(amount)
    if amount == 0:
        raise ValueError("Adjustment amount must not be zero")
    ref_id = secrets.token_hex(8)
    ledger = _append_ledger_entry(
        session=session,
        wallet=wallet,
        organization=organization,
        amount_delta=amount,
        entry_type=adjustment_type,
        actor_label=operator_label,
        note=reason,
        reference_type="admin_adjustment",
        reference_id=ref_id,
        idempotency_key=f"admin-adjustment:{ref_id}",
        metadata_json={"reason": reason, "adjustment_type": adjustment_type},
    )
    record = AdminTopUp(
        wallet_account_id=wallet.id,
        organization_id=organization.id,
        amount=amount,
        operator_label=operator_label,
        reason=reason,
        ledger_entry_id=ledger.id,
    )
    session.add(record)
    session.add(
        AuditLog(
            organization_id=organization.id,
            actor_label=operator_label,
            action=adjustment_type,
            subject_type="wallet_account",
            subject_id=wallet.id,
            details_json={"amount": amount, "reason": reason},
        )
    )
    session.flush()
    return {
        "organization_name": organization.name,
        "wallet_balance": wallet.cached_balance,
        "ledger_entry_id": ledger.id,
    }


@dataclass
class RedeemBatchResult:
    batch_id: str
    name: str
    credit_amount: int
    created_count: int
    codes: list[str]


def create_redeem_batch(
    session,
    name: str,
    credit_amount: int,
    code_count: int,
    operator_label: str,
    prefix: str = "TEMU",
    valid_days: int = 30,
    notes: str = "",
) -> RedeemBatchResult:
    organization = ensure_default_organization(session)
    expires_at = None
    if int(valid_days) > 0:
        expires_at = datetime.utcnow() + timedelta(days=int(valid_days))
    batch = RedeemCodeBatch(
        organization_id=organization.id,
        name=name,
        code_prefix=prefix,
        credit_amount=int(credit_amount),
        code_count=int(code_count),
        expires_at=expires_at,
        created_by_label=operator_label,
        notes=notes,
    )
    session.add(batch)
    session.flush()

    codes: list[str] = []
    for _ in range(int(code_count)):
        while True:
            raw_code = generate_redeem_code(prefix=prefix)
            digest = hash_redeem_code(raw_code)
            exists = session.scalar(
                select(RedeemCode).where(RedeemCode.code_hash == digest)
            )
            if exists is None:
                break
        codes.append(raw_code)
        session.add(
            RedeemCode(
                batch_id=batch.id,
                organization_id=organization.id,
                code_hash=digest,
                code_preview=preview_redeem_code(raw_code),
                credit_amount=int(credit_amount),
                max_redemptions=1,
                expires_at=expires_at,
            )
        )

    session.add(
        AuditLog(
            organization_id=organization.id,
            actor_label=operator_label,
            action="create_redeem_batch",
            subject_type="redeem_code_batch",
            subject_id=batch.id,
            details_json={
                "name": name,
                "code_count": code_count,
                "credit_amount": credit_amount,
            },
        )
    )
    session.flush()
    return RedeemBatchResult(
        batch_id=batch.id,
        name=batch.name,
        credit_amount=batch.credit_amount,
        created_count=code_count,
        codes=codes,
    )


def redeem_code_to_default_wallet(session, raw_code: str, actor_label: str) -> dict:
    organization = ensure_default_organization(session)
    wallet = get_or_create_org_wallet(session, organization)
    digest = hash_redeem_code(raw_code)
    code = session.scalar(select(RedeemCode).where(RedeemCode.code_hash == digest))
    if code is None:
        raise ValueError("Redeem code not found")
    if code.status != "active":
        raise ValueError(f"Redeem code is {code.status}")
    if code.expires_at and code.expires_at < datetime.utcnow():
        code.status = "expired"
        raise ValueError("Redeem code has expired")
    if int(code.redemption_count or 0) >= int(code.max_redemptions or 1):
        code.status = "redeemed"
        raise ValueError("Redeem code has already been used")

    redemption_ref = secrets.token_hex(8)
    ledger = _append_ledger_entry(
        session=session,
        wallet=wallet,
        organization=organization,
        amount_delta=int(code.credit_amount),
        entry_type="redeem_credit",
        actor_label=actor_label,
        note=f"Redeem code {code.code_preview}",
        reference_type="redeem_code",
        reference_id=code.id,
        idempotency_key=f"redeem-code:{code.id}:{redemption_ref}",
        metadata_json={"code_preview": code.code_preview},
    )
    session.add(
        RedeemCodeRedemption(
            code_id=code.id,
            batch_id=code.batch_id,
            wallet_account_id=wallet.id,
            organization_id=organization.id,
            redeemed_by_label=actor_label,
            credit_amount=code.credit_amount,
            ledger_entry_id=ledger.id,
            idempotency_key=ledger.idempotency_key,
        )
    )
    code.redemption_count = int(code.redemption_count or 0) + 1
    code.last_redeemed_at = datetime.utcnow()
    if code.redemption_count >= code.max_redemptions:
        code.status = "redeemed"
    session.add(
        AuditLog(
            organization_id=organization.id,
            actor_label=actor_label,
            action="redeem_code",
            subject_type="redeem_code",
            subject_id=code.id,
            details_json={
                "code_preview": code.code_preview,
                "credit_amount": code.credit_amount,
            },
        )
    )
    session.flush()
    return {
        "organization_name": organization.name,
        "wallet_balance": wallet.cached_balance,
        "code_preview": code.code_preview,
        "credit_amount": code.credit_amount,
    }


def get_wallet_dashboard(session) -> dict:
    organization = ensure_default_organization(session)
    wallet = get_or_create_org_wallet(session, organization)
    total_topups = session.scalar(
        select(func.coalesce(func.sum(AdminTopUp.amount), 0)).where(
            AdminTopUp.wallet_account_id == wallet.id
        )
    )
    total_redeemed = session.scalar(
        select(func.coalesce(func.sum(RedeemCodeRedemption.credit_amount), 0)).where(
            RedeemCodeRedemption.wallet_account_id == wallet.id
        )
    )
    recent_entries = (
        session.execute(
            select(WalletLedgerEntry)
            .where(WalletLedgerEntry.wallet_account_id == wallet.id)
            .order_by(WalletLedgerEntry.created_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    recent_batches = (
        session.execute(
            select(RedeemCodeBatch)
            .where(RedeemCodeBatch.organization_id == organization.id)
            .order_by(RedeemCodeBatch.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    return {
        "organization": organization,
        "wallet": wallet,
        "total_topups": int(total_topups or 0),
        "total_redeemed": int(total_redeemed or 0),
        "recent_entries": recent_entries,
        "recent_batches": recent_batches,
    }
