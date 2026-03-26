from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from .billing import ensure_default_organization
from .models import Organization, UsageEvent


def record_usage_event(
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
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata_json=None,
):
    existing = session.scalar(
        select(UsageEvent).where(UsageEvent.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing
    organization = None
    if organization_id:
        organization = session.scalar(
            select(Organization).where(Organization.id == organization_id)
        )
    if organization is None:
        organization = ensure_default_organization(session)
    event = UsageEvent(
        organization_id=organization.id,
        project_id=project_id or None,
        user_id=user_id or None,
        feature=feature,
        provider=provider,
        model=model,
        charge_source=charge_source,
        request_count=int(request_count),
        output_images=int(output_images),
        tokens_used=int(tokens_used),
        metadata_json={**(metadata_json or {}), "actor_label": actor_label},
        idempotency_key=idempotency_key,
    )
    session.add(event)
    session.flush()
    return event


def list_recent_usage_events(session, limit: int = 20):
    return (
        session.execute(
            select(UsageEvent).order_by(UsageEvent.created_at.desc()).limit(limit)
        )
        .scalars()
        .all()
    )
