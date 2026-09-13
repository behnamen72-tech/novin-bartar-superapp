from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.identity.models import User
from app.core.identity.repository import get_user_by_login
from app.core.identity.security import (
    consume_dummy_password_check,
    hash_password,
    password_hash_needs_rehash,
    verify_password,
)


def authenticate_user(
    session: Session,
    *,
    login: str,
    plain_password: str,
) -> User | None:
    user = get_user_by_login(session, login)

    if user is None:
        consume_dummy_password_check(plain_password)
        return None

    if not verify_password(plain_password, user.password_hash):
        return None

    if not user.is_active or not user.person.is_active:
        return None

    if password_hash_needs_rehash(user.password_hash):
        user.password_hash = hash_password(plain_password)

    user.last_login_at = datetime.now(UTC)
    # The auth route commits last_login, refresh-session creation, and its audit
    # event atomically. Do not commit here.
    session.flush()
    return user
