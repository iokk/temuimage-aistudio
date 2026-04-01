from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    __tablename__ = "User"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="User_issuer_subject_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="personal")
    issuer: Mapped[str] = mapped_column(String(255), nullable=False, default="internal")
    subject: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email_verified: Mapped[bool] = mapped_column(
        "emailVerified", Boolean, nullable=False, default=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column("lastLoginAt", DateTime)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Organization(Base):
    __tablename__ = "Organization"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Project(Base):
    __tablename__ = "Project"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        "organizationId", ForeignKey("Organization.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Membership(Base):
    __tablename__ = "Membership"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        "userId", ForeignKey("User.id"), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        "organizationId", ForeignKey("Organization.id"), nullable=False
    )
    active_project_id: Mapped[str | None] = mapped_column(
        "activeProjectId", ForeignKey("Project.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Credential(Base):
    __tablename__ = "Credential"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_type: Mapped[str] = mapped_column("ownerType", String(32), nullable=False)
    owner_id: Mapped[str] = mapped_column("ownerId", String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_secret: Mapped[str] = mapped_column(
        "encryptedSecret", Text, nullable=False
    )
    config_json: Mapped[dict] = mapped_column("configJson", JSON, default=dict)
    user_id: Mapped[str | None] = mapped_column(
        "userId", ForeignKey("User.id"), nullable=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        "organizationId", ForeignKey("Organization.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Job(Base):
    __tablename__ = "Job"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    owner_id: Mapped[str] = mapped_column(
        "ownerId", ForeignKey("User.id"), nullable=False
    )
    project_id: Mapped[str | None] = mapped_column(
        "projectId", ForeignKey("Project.id"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SystemConfig(Base):
    __tablename__ = "SystemConfig"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_key: Mapped[str] = mapped_column(
        "configKey", String(120), unique=True, nullable=False
    )
    config_value: Mapped[dict] = mapped_column("configValue", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
