from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.admin_schemas import (
    AccessAssignmentCreateRequest,
    AccessAssignmentItem,
    AccessAssignmentStatusRequest,
    AccessOverviewItem,
    PermissionCatalogItem,
    RoleAdminItem,
    RoleCreateRequest,
    RoleStatusRequest,
    RoleUpdateRequest,
)
from app.core.access.admin_service import (
    AccessAdminConflictError,
    AccessAdminNotFoundError,
    AccessAdminValidationError,
    change_access_assignment_status,
    change_role_status,
    create_access_assignment,
    create_role,
    grant_permission_to_role,
    list_access_overview,
    list_permission_catalog,
    list_roles_for_user,
    revoke_permission_from_role,
    update_role,
)
from app.core.access.policy import AuthorizationError, has_permission
from app.core.access.schemas import MyAccessAssignmentResponse, PermissionCheckResponse
from app.core.access.service import list_effective_assignments
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db

router = APIRouter(prefix="/access", tags=["access"])


def _translate_admin_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, AccessAdminNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (AccessAdminConflictError, IntegrityError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (AccessAdminValidationError, ValueError)):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("/me", response_model=list[MyAccessAssignmentResponse])
def read_my_access(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[MyAccessAssignmentResponse]:
    return list_effective_assignments(session, user_id=current_user.id)


@router.get("/overview", response_model=list[AccessOverviewItem])
def read_access_overview(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[AccessOverviewItem]:
    return list_access_overview(session, viewer_user_id=current_user.id)


@router.get("/permissions", response_model=list[PermissionCatalogItem])
def read_permission_catalog(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[PermissionCatalogItem]:
    return list_permission_catalog(session, viewer_user_id=current_user.id)


@router.get("/roles", response_model=list[RoleAdminItem])
def read_roles(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[RoleAdminItem]:
    return list_roles_for_user(session, viewer_user_id=current_user.id)


@router.post("/roles", response_model=RoleAdminItem, status_code=status.HTTP_201_CREATED)
def create_role_endpoint(
    payload: RoleCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RoleAdminItem:
    try:
        return create_role(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.patch("/roles/{role_id}", response_model=RoleAdminItem)
def update_role_endpoint(
    role_id: UUID,
    payload: RoleUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RoleAdminItem:
    try:
        return update_role(session, actor=current_user, role_id=role_id, payload=payload)
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.patch("/roles/{role_id}/status", response_model=RoleAdminItem)
def change_role_status_endpoint(
    role_id: UUID,
    payload: RoleStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RoleAdminItem:
    try:
        return change_role_status(session, actor=current_user, role_id=role_id, payload=payload)
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.post("/roles/{role_id}/permissions/{permission_code}", response_model=RoleAdminItem)
def grant_role_permission_endpoint(
    role_id: UUID,
    permission_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RoleAdminItem:
    try:
        return grant_permission_to_role(
            session,
            actor=current_user,
            role_id=role_id,
            permission_code=permission_code,
        )
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.delete("/roles/{role_id}/permissions/{permission_code}", response_model=RoleAdminItem)
def revoke_role_permission_endpoint(
    role_id: UUID,
    permission_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RoleAdminItem:
    try:
        return revoke_permission_from_role(
            session,
            actor=current_user,
            role_id=role_id,
            permission_code=permission_code,
        )
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.post(
    "/assignments", response_model=AccessAssignmentItem, status_code=status.HTTP_201_CREATED
)
def create_assignment_endpoint(
    payload: AccessAssignmentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> AccessAssignmentItem:
    try:
        return create_access_assignment(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.patch("/assignments/{assignment_id}/status", response_model=AccessAssignmentItem)
def change_assignment_status_endpoint(
    assignment_id: UUID,
    payload: AccessAssignmentStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> AccessAssignmentItem:
    try:
        return change_access_assignment_status(
            session,
            actor=current_user,
            assignment_id=assignment_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        AccessAdminNotFoundError,
        AccessAdminConflictError,
        AccessAdminValidationError,
        ValueError,
        IntegrityError,
    ) as exc:
        session.rollback()
        raise _translate_admin_error(exc) from exc


@router.get(
    "/organizations/{organization_id}/permissions/{permission_code}",
    response_model=PermissionCheckResponse,
)
def check_my_permission(
    organization_id: UUID,
    permission_code: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> PermissionCheckResponse:
    allowed = has_permission(
        session,
        user_id=current_user.id,
        permission_code=permission_code,
        organization_id=organization_id,
    )
    return PermissionCheckResponse(
        organization_id=organization_id,
        permission=permission_code,
        allowed=allowed,
    )
