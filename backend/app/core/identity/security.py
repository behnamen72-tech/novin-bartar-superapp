from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jwt.exceptions import InvalidTokenError

from app.core.config import settings

_password_hasher = PasswordHasher()

# Used only to consume approximately the same password-hash work when a login
# identifier does not exist. This reduces simple username-enumeration timing leaks.
_DUMMY_PASSWORD_HASH = _password_hasher.hash("novin-bartar-superapp-dummy-password-not-a-real-user")


class TokenValidationError(ValueError):
    pass


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def consume_dummy_password_check(plain_password: str) -> None:
    verify_password(plain_password, _DUMMY_PASSWORD_HASH)


def password_hash_needs_rehash(password_hash: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(
    user_id: UUID,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expire,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={
                "require": ["sub", "type", "iat", "exp", "iss", "aud"],
            },
        )
    except InvalidTokenError as exc:
        raise TokenValidationError("Invalid access token.") from exc

    if payload.get("type") != "access":
        raise TokenValidationError("Invalid token type.")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise TokenValidationError("Invalid token subject.")

    try:
        return UUID(subject)
    except ValueError as exc:
        raise TokenValidationError("Invalid token subject.") from exc
