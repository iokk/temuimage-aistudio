from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import secrets
import string
from typing import Optional

from sqlalchemy import func, select

from .models import (
    AdminTopUp,
    AuditLog,
    Organization,
    PricingRule,
    RedeemCode,
    RedeemCodeBatch,
    RedeemCodeRedemption,
    WalletAccount,
    WalletLedgerEntry,
)
from .settings import get_platform_settings


ALPHABET = string.ascii_uppercase + string.digits

DEFAULT_PRICING_RULES = [
    {
        "feature": "combo_image_generation",
        "provider": "*",
        "model": "*",
        "unit_type": "per_output_image",
        "price_amount": 100,
        "status": "active",
        "notes": "Default cost per generated combo image",
    },
    {
        "feature": "smart_image_generation",
        "provider": "*",
        "model": "*",
        "unit_type": "per_output_image",
        "price_amount": 100,
        "status": "active",
        "notes": "Default cost per generated quick image",
    },
    {
        "feature": "image_translate",
        "provider": "*",
        "model": "*",
        "unit_type": "per_output_image",
        "price_amount": 120,
        "status": "active",
        "notes": "Default cost per translated output image",
    },
    {
        "feature": "title_optimization",
        "provider": "Gemini",
        "model": "*",
        "unit_type": "per_request",
        "price_amount": 8,
        "status": "active",
        "notes": "Default low-cost title optimization via Gemini text path",
    },
]


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
    from .team import ensure_workspace_project

    project = ensure_workspace_project(
        session,
        org,
        name=get_platform_settings().default_project_name,
        actor_label="platform-bootstrap",
    )
    ensure_default_pricing_rules(session)
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        "wallet_id": wallet.id,
        "wallet_balance": wallet.cached_balance,
        "project_id": project.id,
        "project_name": project.name,
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
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
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
        project_id=project_id,
        user_id=user_id,
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


def ensure_default_pricing_rules(session) -> list[PricingRule]:
    rules: list[PricingRule] = []
    for spec in DEFAULT_PRICING_RULES:
        rule = session.scalar(
            select(PricingRule).where(
                PricingRule.feature == spec["feature"],
                PricingRule.provider == spec["provider"],
                PricingRule.model == spec["model"],
            )
        )
        if rule is None:
            rule = PricingRule(**spec)
            session.add(rule)
            session.flush()
        rules.append(rule)
    return rules


def list_pricing_rules(session) -> list[PricingRule]:
    ensure_default_pricing_rules(session)
    return (
        session.execute(
            select(PricingRule).order_by(
                PricingRule.feature.asc(),
                PricingRule.provider.asc(),
                PricingRule.model.asc(),
            )
        )
        .scalars()
        .all()
    )


def update_pricing_rule(
    session,
    rule_id: str,
    price_amount: int,
    unit_type: str,
    status: str,
    notes: str,
) -> PricingRule:
    rule = session.scalar(select(PricingRule).where(PricingRule.id == rule_id))
    if rule is None:
        raise ValueError("Pricing rule not found")
    rule.price_amount = int(price_amount)
    rule.unit_type = str(unit_type).strip() or rule.unit_type
    rule.status = str(status).strip() or rule.status
    rule.notes = str(notes or "")
    session.flush()
    return rule


def resolve_pricing_rule(
    session, feature: str, provider: str, model: str
) -> Optional[PricingRule]:
    ensure_default_pricing_rules(session)
    rules = (
        session.execute(
            select(PricingRule).where(
                PricingRule.feature == feature,
                PricingRule.status == "active",
            )
        )
        .scalars()
        .all()
    )
    if not rules:
        return None

    def score(rule: PricingRule) -> tuple[int, int]:
        provider_score = (
            2 if rule.provider == provider else 1 if rule.provider == "*" else 0
        )
        model_score = 2 if rule.model == model else 1 if rule.model == "*" else 0
        return provider_score, model_score

    eligible = [rule for rule in rules if score(rule) > (0, 0)]
    if not eligible:
        return None
    eligible.sort(key=score, reverse=True)
    return eligible[0]


def calculate_usage_charge(
    rule: Optional[PricingRule],
    request_count: int,
    output_images: int,
    tokens_used: int,
) -> int:
    if rule is None:
        return 0
    if rule.unit_type == "per_output_image":
        units = max(int(output_images or 0), 0)
    elif rule.unit_type == "per_request":
        units = max(int(request_count or 0), 1)
    elif rule.unit_type == "per_1k_tokens":
        units = max((int(tokens_used or 0) + 999) // 1000, 1)
    else:
        units = 1
    return int(rule.price_amount or 0) * units


def charge_usage_to_wallet(
    session,
    feature: str,
    provider: str,
    model: str,
    request_count: int,
    output_images: int,
    tokens_used: int,
    charge_source: str,
    actor_label: str,
    idempotency_key: str,
    organization_id: str = "",
    project_id: str = "",
    user_id: str = "",
    metadata_json=None,
) -> dict:
    from .usage import record_usage_event

    organization = None
    if organization_id:
        organization = session.scalar(
            select(Organization).where(Organization.id == organization_id)
        )
    if organization is None:
        organization = ensure_default_organization(session)
    wallet = get_or_create_org_wallet(session, organization)
    usage_event = record_usage_event(
        session,
        feature=feature,
        provider=provider,
        model=model,
        request_count=request_count,
        output_images=output_images,
        tokens_used=tokens_used,
        charge_source=charge_source,
        actor_label=actor_label,
        idempotency_key=f"usage-event:{idempotency_key}",
        organization_id=organization.id,
        project_id=project_id or None,
        user_id=user_id or None,
        metadata_json=metadata_json,
    )
    pricing_rule = resolve_pricing_rule(
        session, feature=feature, provider=provider, model=model
    )
    charge_amount = 0
    ledger = None
    if charge_source == "system_pool":
        charge_amount = calculate_usage_charge(
            pricing_rule,
            request_count=request_count,
            output_images=output_images,
            tokens_used=tokens_used,
        )
        if charge_amount > 0:
            ledger = _append_ledger_entry(
                session=session,
                wallet=wallet,
                organization=organization,
                amount_delta=-int(charge_amount),
                entry_type="usage_debit",
                actor_label=actor_label,
                note=f"{feature} usage charge",
                reference_type="usage_event",
                reference_id=usage_event.id,
                idempotency_key=f"usage-debit:{idempotency_key}",
                project_id=project_id or None,
                user_id=user_id or None,
                metadata_json={
                    "feature": feature,
                    "provider": provider,
                    "model": model,
                    "pricing_rule_id": pricing_rule.id if pricing_rule else "",
                    **(metadata_json or {}),
                },
            )
            session.add(
                AuditLog(
                    organization_id=organization.id,
                    actor_label=actor_label,
                    action="usage_debit",
                    subject_type="usage_event",
                    subject_id=usage_event.id,
                    details_json={
                        "feature": feature,
                        "charge_amount": charge_amount,
                        "project_id": project_id or "",
                    },
                )
            )
            session.flush()
    return {
        "organization_id": organization.id,
        "wallet_id": wallet.id,
        "wallet_balance": int(wallet.cached_balance),
        "usage_event_id": usage_event.id,
        "ledger_entry_id": ledger.id if ledger is not None else "",
        "charge_amount": int(charge_amount),
        "pricing_rule_id": pricing_rule.id if pricing_rule is not None else "",
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
    ensure_default_pricing_rules(session)
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
    total_usage_debits = session.scalar(
        select(func.coalesce(func.sum(WalletLedgerEntry.amount_delta), 0)).where(
            WalletLedgerEntry.wallet_account_id == wallet.id,
            WalletLedgerEntry.entry_type == "usage_debit",
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
        "total_usage_debits": abs(int(total_usage_debits or 0)),
        "recent_entries": recent_entries,
        "recent_batches": recent_batches,
    }
