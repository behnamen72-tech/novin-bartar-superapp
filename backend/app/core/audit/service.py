from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access.permissions import AUDIT_READ
from app.core.access.policy import AuthorizationError, has_permission
from app.core.access.service import authorized_organization_ids
from app.core.audit.models import AuditEvent
from app.core.audit.security import sanitize_audit_payload
from app.core.identity.models import User


def record_audit_event(
    session: Session,
    *,
    actor: User | None,
    organization_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | UUID,
    before_state: dict[str, object] | None = None,
    after_state: dict[str, object] | None = None,
    metadata: dict[str, object] | None = None,
    source: str = "api",
    request_id: str | None = None,
) -> AuditEvent:
    normalized_action = action.strip().lower()
    normalized_resource_type = resource_type.strip().lower()
    normalized_resource_id = str(resource_id).strip()

    if not normalized_action:
        raise ValueError("Audit action cannot be empty.")
    if not normalized_resource_type:
        raise ValueError("Audit resource_type cannot be empty.")
    if not normalized_resource_id:
        raise ValueError("Audit resource_id cannot be empty.")

    event = AuditEvent(
        actor_user_id=actor.id if actor is not None else None,
        actor_identifier=actor.email if actor is not None else None,
        organization_id=organization_id,
        action=normalized_action,
        resource_type=normalized_resource_type,
        resource_id=normalized_resource_id,
        before_state=sanitize_audit_payload(before_state),
        after_state=sanitize_audit_payload(after_state),
        event_metadata=sanitize_audit_payload(metadata),
        source=source.strip().lower() or "api",
        request_id=request_id,
    )
    session.add(event)
    return event


def list_audit_events_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEvent]:
    if organization_id is not None:
        if not has_permission(
            session,
            user_id=user_id,
            permission_code=AUDIT_READ,
            organization_id=organization_id,
        ):
            raise AuthorizationError("Permission denied.")
        allowed_organization_ids = {organization_id}
    else:
        allowed_organization_ids = authorized_organization_ids(
            session,
            user_id=user_id,
            permission_code=AUDIT_READ,
        )

    if not allowed_organization_ids:
        return []

    statement = (
        select(AuditEvent)
        .where(AuditEvent.organization_id.in_(allowed_organization_ids))
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(session.scalars(statement).all())
