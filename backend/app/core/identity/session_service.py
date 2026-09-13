from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.identity.models import User, UserSession


class RefreshSessionError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedRefreshToken:
    token: str
    expires_in: int
    user_session: UserSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    # 48 random bytes provides substantially more than 256 bits of entropy after
    # URL-safe encoding. Only the SHA-256 digest is persisted.
    return secrets.token_urlsafe(48)


def refresh_token_lifetime_seconds() -> int:
    return settings.auth_refresh_token_expire_days * 24 * 60 * 60


def create_refresh_session(session: Session, *, user: User) -> IssuedRefreshToken:
    now = _now()
    token = _new_refresh_token()
    lifetime = refresh_token_lifetime_seconds()
    user_session = UserSession(
        user=user,
        refresh_token_hash=_refresh_token_hash(token),
        expires_at=now + timedelta(seconds=lifetime),
    )
    session.add(user_session)
    session.flush()
    return IssuedRefreshToken(token=token, expires_in=lifetime, user_session=user_session)


def rotate_refresh_session(
    session: Session,
    *,
    refresh_token: str,
) -> tuple[User, IssuedRefreshToken]:
    normalized = refresh_token.strip()
    if not normalized:
        raise RefreshSessionError("Invalid refresh token.")

    token_hash = _refresh_token_hash(normalized)
    statement = (
        select(UserSession)
        .options(joinedload(UserSession.user).joinedload(User.person))
        .where(UserSession.refresh_token_hash == token_hash)
        .with_for_update()
    )
    user_session = session.scalar(statement)
    now = _now()

    if (
        user_session is None
        or user_session.revoked_at is not None
        or _as_utc(user_session.expires_at) <= now
    ):
        raise RefreshSessionError("Invalid refresh token.")

    user = user_session.user
    if not user.is_active or not user.person.is_active:
        raise RefreshSessionError("Invalid refresh token.")

    new_token = _new_refresh_token()
    remaining_lifetime = max(1, int((_as_utc(user_session.expires_at) - now).total_seconds()))
    user_session.refresh_token_hash = _refresh_token_hash(new_token)
    user_session.last_used_at = now
    # Rotation does not extend the absolute authenticated-session lifetime.
    # A user must perform a full password login again after the configured period.
    session.flush()

    return user, IssuedRefreshToken(
        token=new_token,
        expires_in=remaining_lifetime,
        user_session=user_session,
    )


def revoke_refresh_session(
    session: Session,
    *,
    refresh_token: str,
) -> UserSession | None:
    normalized = refresh_token.strip()
    if not normalized:
        return None

    statement = (
        select(UserSession)
        .options(joinedload(UserSession.user))
        .where(UserSession.refresh_token_hash == _refresh_token_hash(normalized))
        .with_for_update()
    )
    user_session = session.scalar(statement)
    if user_session is None:
        return None

    if user_session.revoked_at is not None:
        return None

    user_session.revoked_at = _now()
    session.flush()
    return user_session
