from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.identity.models import User
from app.core.identity.security import TokenValidationError, decode_access_token
from app.db.session import get_db


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        user_id = decode_access_token(token)
    except TokenValidationError as exc:
        raise credentials_exception() from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active or not user.person.is_active:
        raise credentials_exception()

    return user
