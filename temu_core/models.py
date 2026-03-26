from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    auth_provider: Mapped[str] = mapped_column(
        String(32), default="synthetic", nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    billing_mode: Mapped[str] = mapped_column(
        String(32), default="org_wallet", nullable=False
    )

    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization"
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")


class OrganizationMember(TimestampMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="projects")


class WalletAccount(TimestampMixin, Base):
    __tablename__ = "wallet_accounts"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uq_wallet_owner"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="credits", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    cached_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class WalletLedgerEntry(Base):
    __tablename__ = "wallet_ledger_entries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_wallet_ledger_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount_delta: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    reference_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    actor_label: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[object] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class AdminTopUp(TimestampMixin, Base):
    __tablename__ = "admin_topups"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_label: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ledger_entry_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_ledger_entries.id", ondelete="CASCADE"), nullable=False
    )


class RedeemCodeBatch(TimestampMixin, Base):
    __tablename__ = "redeem_code_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code_prefix: Mapped[str] = mapped_column(String(32), default="TEMU", nullable=False)
    credit_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_redemptions_per_code: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_by_label: Mapped[str] = mapped_column(
        String(160), default="", nullable=False
    )
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class RedeemCode(TimestampMixin, Base):
    __tablename__ = "redeem_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("redeem_code_batches.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    code_preview: Mapped[str] = mapped_column(String(32), nullable=False)
    credit_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    max_redemptions: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    redemption_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class RedeemCodeRedemption(Base):
    __tablename__ = "redeem_code_redemptions"
    __table_args__ = (
        UniqueConstraint(
            "code_id", "idempotency_key", name="uq_code_redemption_idempotency"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code_id: Mapped[str] = mapped_column(
        ForeignKey("redeem_codes.id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("redeem_code_batches.id", ondelete="CASCADE"), nullable=False
    )
    wallet_account_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_accounts.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    redeemed_by_label: Mapped[str] = mapped_column(
        String(160), default="", nullable=False
    )
    credit_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ledger_entry_id: Mapped[str] = mapped_column(
        ForeignKey("wallet_ledger_entries.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_usage_event_idempotency"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    feature: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    charge_source: Mapped[str] = mapped_column(
        String(40), default="system_pool", nullable=False
    )
    request_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    output_images: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    metadata_json: Mapped[object] = mapped_column(JSON)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class PricingRule(TimestampMixin, Base):
    __tablename__ = "pricing_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    feature: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_type: Mapped[str] = mapped_column(String(40), nullable=False)
    price_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class PlatformConfig(TimestampMixin, Base):
    __tablename__ = "platform_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    config_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    config_value_json: Mapped[object] = mapped_column(JSON)
    encrypted_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_by_label: Mapped[str] = mapped_column(
        String(160), default="", nullable=False
    )


class UserBackup(Base):
    __tablename__ = "user_backups"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    original_user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    email: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    deleted_by_label: Mapped[str] = mapped_column(
        String(160), default="", nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    snapshot_json: Mapped[object] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL")
    )
    actor_label: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    details_json: Mapped[object] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


EXPECTED_TABLES = [
    "users",
    "organizations",
    "organization_members",
    "projects",
    "wallet_accounts",
    "wallet_ledger_entries",
    "admin_topups",
    "redeem_code_batches",
    "redeem_codes",
    "redeem_code_redemptions",
    "usage_events",
    "pricing_rules",
    "platform_configs",
    "user_backups",
    "audit_logs",
]
