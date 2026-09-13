from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.audit.service import record_audit_event
from app.core.config import settings
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.core.identity.schemas import CurrentUserResponse, RefreshTokenRequest, TokenResponse
from app.core.identity.security import create_access_token
from app.core.identity.service import authenticate_user
from app.core.identity.session_service import (
    RefreshSessionError,
    create_refresh_session,
    revoke_refresh_session,
    rotate_refresh_session,
)
from app.db.session import get_db


router = APIRouter(prefix="/auth", tags=["authentication"])


def _access_lifetime_seconds() -> int:
    return settings.jwt_access_token_expire_minutes * 60


def _token_response(*, user: User, refresh_token: str, refresh_expires_in: int) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=_access_lifetime_seconds(),
        refresh_token=refresh_token,
        refresh_expires_in=refresh_expires_in,
    )


@router.post("/token", response_model=TokenResponse)
def issue_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(
        session,
        login=form_data.username,
        plain_password=form_data.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    issued = create_refresh_session(session, user=user)
    record_audit_event(
        session,
        actor=user,
        organization_id=None,
        action="auth.login.succeeded",
        resource_type="user_session",
        resource_id=issued.user_session.id,
        metadata={"authentication_method": "password"},
    )
    session.commit()

    return _token_response(
        user=user,
        refresh_token=issued.token,
        refresh_expires_in=issued.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    payload: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    try:
        user, issued = rotate_refresh_session(
            session,
            refresh_token=payload.refresh_token.get_secret_value(),
        )
    except RefreshSessionError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    record_audit_event(
        session,
        actor=user,
        organization_id=None,
        action="auth.session.refreshed",
        resource_type="user_session",
        resource_id=issued.user_session.id,
    )
    session.commit()

    return _token_response(
        user=user,
        refresh_token=issued.token,
        refresh_expires_in=issued.expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_session(
    payload: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    user_session = revoke_refresh_session(
        session,
        refresh_token=payload.refresh_token.get_secret_value(),
    )
    if user_session is not None:
        record_audit_event(
            session,
            actor=user_session.user,
            organization_id=None,
            action="auth.logout",
            resource_type="user_session",
            resource_id=user_session.id,
        )
        session.commit()
    else:
        session.rollback()

    # Logout is intentionally idempotent: an already-invalid token must not reveal
    # whether a server-side session record existed.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(current_user)
