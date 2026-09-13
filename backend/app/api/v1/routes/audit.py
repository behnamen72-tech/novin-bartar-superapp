from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.audit.schemas import AuditEventResponse
from app.core.audit.service import list_audit_events_for_user
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventResponse])
def list_audit_events(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    organization_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEventResponse]:
    try:
        events = list_audit_events_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        ) from exc

    return [AuditEventResponse.model_validate(event) for event in events]
