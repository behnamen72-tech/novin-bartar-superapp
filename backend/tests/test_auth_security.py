from datetime import timedelta
from uuid import uuid4

import jwt

from app.core.config import settings
from app.core.identity.security import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifiable() -> None:
    plain = "A-secure-test-password-123!"
    password_hash = hash_password(plain)

    assert password_hash != plain
    assert password_hash.startswith("$argon2")
    assert verify_password(plain, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)

    assert decode_access_token(token) == user_id


def test_expired_access_token_is_rejected() -> None:
    user_id = uuid4()
    token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))

    try:
        decode_access_token(token)
    except TokenValidationError:
        pass
    else:
        raise AssertionError("Expired token must be rejected")


def test_token_payload_does_not_contain_password_data() -> None:
    user_id = uuid4()
    token = create_access_token(user_id)

    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )

    assert payload["sub"] == str(user_id)
    assert "password" not in payload
    assert "password_hash" not in payload



def test_example_jwt_secret_is_rejected() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    try:
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="replace-with-a-random-secret-of-at-least-32-characters",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Example JWT secret must not be accepted")


def test_access_tokens_have_unique_jti() -> None:
    user_id = uuid4()
    first = create_access_token(user_id)
    second = create_access_token(user_id)

    assert first != second
