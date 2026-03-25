"""team billing foundation

Revision ID: 20260326_0001
Revises:
Create Date: 2026-03-26 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("username", sa.String(length=120), nullable=False, unique=True),
        sa.Column(
            "display_name", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column(
            "billing_mode",
            sa.String(length=32),
            nullable=False,
            server_default="org_wallet",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "organization_members",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role", sa.String(length=32), nullable=False, server_default="member"
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "wallet_accounts",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "unit", sa.String(length=32), nullable=False, server_default="credits"
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column(
            "cached_balance", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_type", "owner_id", name="uq_wallet_owner"),
    )

    op.create_table(
        "wallet_ledger_entries",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "wallet_account_id",
            sa.String(length=32),
            sa.ForeignKey("wallet_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=32),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("entry_type", sa.String(length=40), nullable=False),
        sa.Column("amount_delta", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column(
            "reference_type", sa.String(length=40), nullable=False, server_default=""
        ),
        sa.Column(
            "reference_id", sa.String(length=64), nullable=False, server_default=""
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column(
            "actor_label", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_wallet_ledger_idempotency"),
    )
    op.create_index(
        "ix_wallet_ledger_wallet_created",
        "wallet_ledger_entries",
        ["wallet_account_id", "created_at"],
    )

    op.create_table(
        "admin_topups",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "wallet_account_id",
            sa.String(length=32),
            sa.ForeignKey("wallet_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("operator_label", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "ledger_entry_id",
            sa.String(length=32),
            sa.ForeignKey("wallet_ledger_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "redeem_code_batches",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "code_prefix", sa.String(length=32), nullable=False, server_default="TEMU"
        ),
        sa.Column("credit_amount", sa.BigInteger(), nullable=False),
        sa.Column("code_count", sa.Integer(), nullable=False),
        sa.Column(
            "max_redemptions_per_code", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column(
            "created_by_label", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "redeem_codes",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=32),
            sa.ForeignKey("redeem_code_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("code_preview", sa.String(length=32), nullable=False),
        sa.Column("credit_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("max_redemptions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("redemption_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("last_redeemed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "redeem_code_redemptions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "code_id",
            sa.String(length=32),
            sa.ForeignKey("redeem_codes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "batch_id",
            sa.String(length=32),
            sa.ForeignKey("redeem_code_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wallet_account_id",
            sa.String(length=32),
            sa.ForeignKey("wallet_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "redeemed_by_label",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("credit_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "ledger_entry_id",
            sa.String(length=32),
            sa.ForeignKey("wallet_ledger_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "code_id", "idempotency_key", name="uq_code_redemption_idempotency"
        ),
    )

    op.create_table(
        "usage_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(length=32),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "user_id",
            sa.String(length=32),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("feature", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "charge_source",
            sa.String(length=40),
            nullable=False,
            server_default="system_pool",
        ),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("output_images", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_usage_event_idempotency"),
    )

    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("feature", sa.String(length=40), nullable=False),
        sa.Column("unit_type", sa.String(length=40), nullable=False),
        sa.Column("price_amount", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="draft"
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=32),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "actor_label", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "subject_type", sa.String(length=80), nullable=False, server_default=""
        ),
        sa.Column(
            "subject_id", sa.String(length=64), nullable=False, server_default=""
        ),
        sa.Column("details_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("pricing_rules")
    op.drop_table("usage_events")
    op.drop_table("redeem_code_redemptions")
    op.drop_table("redeem_codes")
    op.drop_table("redeem_code_batches")
    op.drop_table("admin_topups")
    op.drop_index("ix_wallet_ledger_wallet_created", table_name="wallet_ledger_entries")
    op.drop_table("wallet_ledger_entries")
    op.drop_table("wallet_accounts")
    op.drop_table("projects")
    op.drop_table("organization_members")
    op.drop_table("organizations")
    op.drop_table("users")
