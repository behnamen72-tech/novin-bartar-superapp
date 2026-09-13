from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.permissions import USERS_MANAGE
from app.core.access.policy import AuthorizationError
from app.core.identity.admin_schemas import (
    UserCreateRequest,
    UserListItem,
    UserPasswordResetRequest,
    UserStatusRequest,
    UserUpdateRequest,
)
from app.core.identity.admin_service import (
    UserAdminConflictError,
    UserAdminNotFoundError,
    change_user_status,
    create_user,
    get_user_for_viewer,
    list_users_for_user,
    reset_user_password,
    update_user,
)
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db

router = APIRouter(prefix="/users", tags=["users"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, UserAdminNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, UserAdminConflictError) or isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[UserListItem])
def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[UserListItem]:
    return list_users_for_user(session, user_id=current_user.id)


@router.get("/{user_id}", response_model=UserListItem)
def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    try:
        return get_user_for_viewer(session, viewer_user_id=current_user.id, target_user_id=user_id)
    except UserAdminNotFoundError as exc:
        raise _translate_error(exc) from exc


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    try:
        user = create_user(session, actor=current_user, payload=payload)
        return get_user_for_viewer(
            session,
            viewer_user_id=current_user.id,
            target_user_id=user.id,
            permission_code=USERS_MANAGE,
        )
    except (AuthorizationError, UserAdminNotFoundError, UserAdminConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch("/{user_id}", response_model=UserListItem)
def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    try:
        user = update_user(session, actor=current_user, target_user_id=user_id, payload=payload)
        return get_user_for_viewer(
            session,
            viewer_user_id=current_user.id,
            target_user_id=user.id,
            permission_code=USERS_MANAGE,
        )
    except (AuthorizationError, UserAdminNotFoundError, UserAdminConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch("/{user_id}/status", response_model=UserListItem)
def change_user_status_endpoint(
    user_id: UUID,
    payload: UserStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    try:
        user = change_user_status(session, actor=current_user, target_user_id=user_id, payload=payload)
        return get_user_for_viewer(
            session,
            viewer_user_id=current_user.id,
            target_user_id=user.id,
            permission_code=USERS_MANAGE,
        )
    except (AuthorizationError, UserAdminNotFoundError, UserAdminConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.post("/{user_id}/password-reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password_endpoint(
    user_id: UUID,
    payload: UserPasswordResetRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        reset_user_password(session, actor=current_user, target_user_id=user_id, payload=payload)
    except (AuthorizationError, UserAdminNotFoundError, UserAdminConflictError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
