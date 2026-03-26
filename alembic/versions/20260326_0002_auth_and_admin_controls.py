"""auth and admin controls

Revision ID: 20260326_0002
Revises: 20260326_0001
Create Date: 2026-03-26 00:02:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0002"
down_revision = "20260326_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(length=32),
            nullable=False,
            server_default="synthetic",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.create_table(
        "platform_configs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("config_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("config_value_json", sa.JSON()),
        sa.Column("encrypted_value", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_by_label",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "user_backups",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("original_user_id", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column(
            "display_name", sa.String(length=160), nullable=False, server_default=""
        ),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column(
            "deleted_by_label",
            sa.String(length=160),
            nullable=False,
            server_default="",
        ),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("snapshot_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_backups")
    op.drop_table("platform_configs")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "auth_provider")
