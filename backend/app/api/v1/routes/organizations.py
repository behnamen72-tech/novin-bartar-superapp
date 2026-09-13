from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.permissions import ORGANIZATION_MANAGE, ORGANIZATION_READ
from app.core.access.policy import AuthorizationError
from app.core.access.service import (
    list_authorized_organizations,
    list_visible_organizations_for_management,
)
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.core.organization.schemas import (
    OrganizationCreateRequest,
    OrganizationListItem,
    OrganizationStatusRequest,
    OrganizationUpdateRequest,
)
from app.core.organization.service import (
    OrganizationConflictError,
    OrganizationNotFoundError,
    OrganizationValidationError,
    change_organization_status,
    create_organization,
    update_organization,
)
from app.db.session import get_db

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _translate_write_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, OrganizationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, OrganizationConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (OrganizationValidationError, ValueError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Organization write conflict."
        )
    raise exc


@router.get("", response_model=list[OrganizationListItem])
def list_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = False,
) -> list[OrganizationListItem]:
    if include_inactive:
        organizations = list_visible_organizations_for_management(
            session,
            user_id=current_user.id,
            read_permission_code=ORGANIZATION_READ,
            manage_permission_code=ORGANIZATION_MANAGE,
        )
    else:
        organizations = list_authorized_organizations(
            session,
            user_id=current_user.id,
            permission_code=ORGANIZATION_READ,
        )
    return [OrganizationListItem.model_validate(organization) for organization in organizations]


@router.post("", response_model=OrganizationListItem, status_code=status.HTTP_201_CREATED)
def create_organization_endpoint(
    payload: OrganizationCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> OrganizationListItem:
    try:
        organization = create_organization(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        OrganizationNotFoundError,
        OrganizationConflictError,
        OrganizationValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_write_error(exc) from exc
    return OrganizationListItem.model_validate(organization)


@router.patch("/{organization_id}", response_model=OrganizationListItem)
def update_organization_endpoint(
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> OrganizationListItem:
    try:
        organization = update_organization(
            session,
            actor=current_user,
            organization_id=organization_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        OrganizationNotFoundError,
        OrganizationConflictError,
        OrganizationValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_write_error(exc) from exc
    return OrganizationListItem.model_validate(organization)


@router.patch("/{organization_id}/status", response_model=OrganizationListItem)
def change_organization_status_endpoint(
    organization_id: UUID,
    payload: OrganizationStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> OrganizationListItem:
    try:
        organization = change_organization_status(
            session,
            actor=current_user,
            organization_id=organization_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        OrganizationNotFoundError,
        OrganizationConflictError,
        OrganizationValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_write_error(exc) from exc
    return OrganizationListItem.model_validate(organization)
