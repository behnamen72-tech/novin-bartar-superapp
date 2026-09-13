from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.identity.models import User
from app.core.notifications.models import Notification, NotificationSeverity
from app.core.organization.models import Organization


class NotificationNotFoundError(LookupError):
    pass


class NotificationValidationError(ValueError):
    pass


def _clean_required(value: str, *, field: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise NotificationValidationError(f"{field} cannot be empty.")
    if len(normalized) > max_length:
        raise NotificationValidationError(
            f"{field} cannot exceed {max_length} characters."
        )
    return normalized


def _clean_optional(value: str | None, *, field: str, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise NotificationValidationError(
            f"{field} cannot exceed {max_length} characters."
        )
    return normalized


def _validate_action_path(value: str | None) -> str | None:
    path = _clean_optional(value, field="action_path", max_length=500)
    if path is None:
        return None
    # Only app-local paths are allowed. This prevents notification content from
    # becoming an open-redirect or javascript/data URL surface in the UI.
    if (
        not path.startswith("/")
        or path.startswith("//")
        or path.startswith("/\\")
        or "\\" in path
        or "://" in path
        or any(ord(character) < 32 for character in path)
    ):
        raise NotificationValidationError("action_path must be an app-local path.")
    return path


def create_notification(
    session: Session,
    *,
    recipient_user_id: UUID,
    event_code: str,
    title: str,
    body: str | None = None,
    organization_id: UUID | None = None,
    source: str = "system",
    severity: NotificationSeverity = NotificationSeverity.INFO,
    resource_type: str | None = None,
    resource_id: str | None = None,
    action_path: str | None = None,
    dedupe_key: str | None = None,
) -> Notification:
    """Create one durable in-app notification without committing the transaction.

    Domain modules call this function inside their own transaction so the domain
    write and notification are atomic. `dedupe_key`, when supplied, makes retrying
    the same producer operation idempotent for a recipient.
    """

    recipient = session.get(User, recipient_user_id)
    if recipient is None or recipient.person is None:
        raise NotificationValidationError("Recipient user does not exist.")

    if organization_id is not None:
        organization = session.get(Organization, organization_id)
        if organization is None:
            raise NotificationValidationError("Notification organization does not exist.")

    cleaned_dedupe = _clean_optional(dedupe_key, field="dedupe_key", max_length=180)
    if cleaned_dedupe is not None:
        existing = session.scalar(
            select(Notification).where(
                Notification.recipient_user_id == recipient_user_id,
                Notification.dedupe_key == cleaned_dedupe,
            )
        )
        if existing is not None:
            return existing

    cleaned_resource_type = _clean_optional(
        resource_type, field="resource_type", max_length=100
    )
    cleaned_resource_id = _clean_optional(
        resource_id, field="resource_id", max_length=160
    )
    if (cleaned_resource_type is None) != (cleaned_resource_id is None):
        raise NotificationValidationError(
            "resource_type and resource_id must be provided together."
        )

    notification = Notification(
        recipient_user_id=recipient_user_id,
        organization_id=organization_id,
        event_code=_clean_required(event_code, field="event_code", max_length=120),
        source=_clean_required(source, field="source", max_length=100),
        severity=severity,
        title=_clean_required(title, field="title", max_length=180),
        body=_clean_optional(body, field="body", max_length=4000),
        resource_type=cleaned_resource_type,
        resource_id=cleaned_resource_id,
        action_path=_validate_action_path(action_path),
        dedupe_key=cleaned_dedupe,
    )
    session.add(notification)
    session.flush()
    return notification


def list_notifications_for_user(
    session: Session,
    *,
    user_id: UUID,
    unread_only: bool = False,
    organization_id: UUID | None = None,
    event_code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    stmt = select(Notification).where(Notification.recipient_user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if organization_id is not None:
        stmt = stmt.where(Notification.organization_id == organization_id)
    if event_code:
        stmt = stmt.where(Notification.event_code == event_code.strip())
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt).all())


def get_notification_for_user(
    session: Session,
    *,
    user_id: UUID,
    notification_id: UUID,
    lock: bool = False,
) -> Notification:
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.recipient_user_id == user_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    notification = session.scalar(stmt)
    if notification is None:
        raise NotificationNotFoundError("Notification not found.")
    return notification


def unread_count_for_user(session: Session, *, user_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_user_id == user_id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )


def mark_notification_read(
    session: Session,
    *,
    user_id: UUID,
    notification_id: UUID,
) -> Notification:
    notification = get_notification_for_user(
        session,
        user_id=user_id,
        notification_id=notification_id,
        lock=True,
    )
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        session.commit()
    return notification


def mark_notification_unread(
    session: Session,
    *,
    user_id: UUID,
    notification_id: UUID,
) -> Notification:
    notification = get_notification_for_user(
        session,
        user_id=user_id,
        notification_id=notification_id,
        lock=True,
    )
    if notification.read_at is not None:
        notification.read_at = None
        session.commit()
    return notification


def mark_all_notifications_read(session: Session, *, user_id: UUID) -> int:
    now = datetime.now(timezone.utc)
    result = session.execute(
        update(Notification)
        .where(
            Notification.recipient_user_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    session.commit()
    return int(result.rowcount or 0)
