from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select

from .billing import ensure_default_organization, slugify_name
from .models import AuditLog, Organization, OrganizationMember, Project, User
from .settings import get_platform_settings


@dataclass
class WorkspaceContext:
    organization_id: str
    organization_name: str
    user_id: str
    username: str
    display_name: str
    role: str
    project_id: str
    project_name: str


def ensure_platform_user(
    session,
    username: str,
    display_name: str = "",
    email: str = "",
    status: str = "active",
) -> User:
    username = slugify_name(username)
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            display_name=display_name or username,
            email=email or "",
            status=status,
        )
        session.add(user)
        session.flush()
    else:
        changed = False
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        if user.status != status:
            user.status = status
            changed = True
        if changed:
            session.flush()
    return user


def ensure_organization_member(
    session, organization: Organization, user: User, role: str = "member"
) -> OrganizationMember:
    membership = session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == user.id,
        )
    )
    if membership is None:
        membership = OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
            status="active",
        )
        session.add(membership)
        session.flush()
    elif membership.role != role or membership.status != "active":
        membership.role = role
        membership.status = "active"
        session.flush()
    return membership


def ensure_workspace_project(
    session,
    organization: Organization,
    name: str,
    actor_label: str = "platform-bootstrap",
) -> Project:
    cleaned_name = (
        str(name or "").strip() or get_platform_settings().default_project_name
    )
    project = session.scalar(
        select(Project).where(
            Project.organization_id == organization.id,
            func.lower(Project.name) == cleaned_name.lower(),
        )
    )
    if project is None:
        project = Project(
            organization_id=organization.id, name=cleaned_name, status="active"
        )
        session.add(project)
        session.flush()
        session.add(
            AuditLog(
                organization_id=organization.id,
                actor_label=actor_label,
                action="create_project",
                subject_type="project",
                subject_id=project.id,
                details_json={"name": cleaned_name},
            )
        )
        session.flush()
    return project


def create_workspace_project(
    session,
    organization: Organization,
    name: str,
    actor_label: str = "streamlit-admin",
) -> Project:
    return ensure_workspace_project(
        session,
        organization=organization,
        name=name,
        actor_label=actor_label,
    )


def ensure_workspace_identity(
    session,
    username: str,
    display_name: str,
    role: str = "member",
    email: str = "",
    project_name: str = "",
) -> WorkspaceContext:
    organization = ensure_default_organization(session)
    user = ensure_platform_user(
        session, username=username, display_name=display_name, email=email
    )
    ensure_organization_member(session, organization, user, role=role)
    project = ensure_workspace_project(
        session,
        organization,
        name=project_name or get_platform_settings().default_project_name,
        actor_label=username,
    )
    return WorkspaceContext(
        organization_id=organization.id,
        organization_name=organization.name,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=role,
        project_id=project.id,
        project_name=project.name,
    )


def list_workspace_projects(session, organization_id: str) -> list[Project]:
    return (
        session.execute(
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.created_at.asc(), Project.name.asc())
        )
        .scalars()
        .all()
    )


def get_membership_for_user(
    session, organization_id: str, user_id: str
) -> Optional[OrganizationMember]:
    return session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )


def get_workspace_context_for_user(
    session, user: User, project_id: str = ""
) -> WorkspaceContext:
    organization = ensure_default_organization(session)
    membership = get_membership_for_user(session, organization.id, user.id)
    if membership is None:
        membership = ensure_organization_member(
            session, organization, user, role="member"
        )
    projects = list_workspace_projects(session, organization.id)
    if not projects:
        project = ensure_workspace_project(
            session,
            organization,
            name=get_platform_settings().default_project_name,
            actor_label=user.username,
        )
    else:
        project = next((p for p in projects if p.id == project_id), projects[0])
    return WorkspaceContext(
        organization_id=organization.id,
        organization_name=organization.name,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=membership.role,
        project_id=project.id,
        project_name=project.name,
    )


def list_workspace_members(session, organization_id: str) -> list[dict]:
    rows = session.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.created_at.asc())
    ).all()
    return [
        {
            "membership_id": member.id,
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": member.role,
            "status": member.status,
            "joined_at": member.created_at,
        }
        for member, user in rows
    ]


def get_workspace_overview(session) -> dict:
    organization = ensure_default_organization(session)
    projects = list_workspace_projects(session, organization.id)
    members = list_workspace_members(session, organization.id)
    return {
        "organization": organization,
        "project_count": len(projects),
        "member_count": len(members),
        "projects": projects,
        "members": members,
    }
