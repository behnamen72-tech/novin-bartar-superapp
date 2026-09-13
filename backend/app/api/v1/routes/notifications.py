from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.core.notifications.schemas import (
    NotificationReadAllResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.core.notifications.service import (
    NotificationNotFoundError,
    get_notification_for_user,
    list_notifications_for_user,
    mark_all_notifications_read,
    mark_notification_read,
    mark_notification_unread,
    unread_count_for_user,
)
from app.db.session import get_db


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_my_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    unread_only: bool = False,
    organization_id: UUID | None = None,
    event_code: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NotificationResponse]:
    items = list_notifications_for_user(
        session,
        user_id=current_user.id,
        unread_only=unread_only,
        organization_id=organization_id,
        event_code=event_code,
        limit=limit,
        offset=offset,
    )
    return [NotificationResponse.model_validate(item) for item in items]


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_my_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> NotificationUnreadCountResponse:
    return NotificationUnreadCountResponse(
        unread_count=unread_count_for_user(session, user_id=current_user.id)
    )


@router.post("/read-all", response_model=NotificationReadAllResponse)
def read_all_my_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> NotificationReadAllResponse:
    return NotificationReadAllResponse(
        marked_read=mark_all_notifications_read(session, user_id=current_user.id)
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_my_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    try:
        item = get_notification_for_user(
            session,
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        ) from exc
    return NotificationResponse.model_validate(item)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_my_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    try:
        item = mark_notification_read(
            session,
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        ) from exc
    return NotificationResponse.model_validate(item)


@router.post("/{notification_id}/unread", response_model=NotificationResponse)
def unread_my_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    try:
        item = mark_notification_unread(
            session,
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        ) from exc
    return NotificationResponse.model_validate(item)
