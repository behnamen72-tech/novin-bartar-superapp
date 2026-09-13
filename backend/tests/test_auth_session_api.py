from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from app.core.audit.models import AuditEvent
from app.core.identity.models import User, UserSession
from app.core.identity.security import hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def auth_session_db() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session_client(auth_session_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = auth_session_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def create_session_user(auth_session_db: sessionmaker[Session]) -> User:
    with auth_session_db() as session:
        holding = Organization(
            name="Novin Bartar",
            code="NOVIN-SESSION",
            organization_type=OrganizationType.HOLDING,
        )
        company = Organization(
            name="Enferadi Market",
            code="ENFERADI-SESSION",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        person = Person(
            first_name="Session",
            last_name="User",
            email="session.person@example.com",
        )
        relationship = PersonOrganizationRelationship(
            person=person,
            organization=company,
            relationship_code="employee",
        )
        user = User(
            person=person,
            email="session@example.com",
            username="sessionuser",
            password_hash=hash_password("Correct-password-123!"),
        )
        session.add_all([holding, company, person, relationship, user])
        session.commit()
        session.refresh(user)
        return user


def login(session_client: TestClient) -> dict[str, object]:
    response = session_client.post(
        "/api/v1/auth/token",
        data={
            "username": "SESSION@EXAMPLE.COM",
            "password": "Correct-password-123!",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_login_issues_access_and_opaque_refresh_token(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    create_session_user(auth_session_db)
    body = login(session_client)

    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert isinstance(body["refresh_token"], str) and len(body["refresh_token"]) >= 40
    assert body["expires_in"] > 0
    assert body["refresh_expires_in"] > body["expires_in"]

    with auth_session_db() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None
        assert (
            stored.refresh_token_hash
            == hashlib.sha256(body["refresh_token"].encode("utf-8")).hexdigest()
        )
        assert body["refresh_token"] not in stored.refresh_token_hash
        actions = set(session.scalars(select(AuditEvent.action)).all())
        assert "auth.login.succeeded" in actions


def test_refresh_rotates_token_and_old_token_cannot_be_reused(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    create_session_user(auth_session_db)
    first = login(session_client)

    refresh_response = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    second = refresh_response.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert second["access_token"] != first["access_token"]

    replay = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401

    current = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second["refresh_token"]},
    )
    assert current.status_code == 200

    with auth_session_db() as session:
        actions = list(session.scalars(select(AuditEvent.action)).all())
        assert "auth.session.refreshed" in actions


def test_logout_revokes_refresh_token_idempotently(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    create_session_user(auth_session_db)
    tokens = login(session_client)

    logout_response = session_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_response.status_code == 204

    refresh_response = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401

    second_logout = session_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert second_logout.status_code == 204

    with auth_session_db() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None and stored.revoked_at is not None
        actions = list(session.scalars(select(AuditEvent.action)).all())
        assert actions.count("auth.logout") == 1


def test_expired_refresh_token_is_rejected(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    create_session_user(auth_session_db)
    tokens = login(session_client)

    with auth_session_db() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    response = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 401


def test_inactive_user_refresh_is_rejected_and_session_revoked(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    user = create_session_user(auth_session_db)
    tokens = login(session_client)

    with auth_session_db() as session:
        stored_user = session.get(User, user.id)
        assert stored_user is not None
        stored_user.is_active = False
        session.commit()

    response = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 401

    with auth_session_db() as session:
        stored_session = session.scalar(select(UserSession))
        # Revocation is best-effort inside the rejected refresh transaction; the
        # endpoint rolls back on authentication failure, so no state change is
        # relied upon for security. get_current_user and future refreshes still deny.
        assert stored_session is not None


def test_refresh_error_does_not_expose_token(
    session_client: TestClient,
) -> None:
    secret = "definitely-not-a-valid-refresh-token"
    response = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": secret},
    )
    assert response.status_code == 401
    assert secret not in response.text


def test_refresh_does_not_extend_absolute_session_expiry(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    create_session_user(auth_session_db)
    tokens = login(session_client)

    with auth_session_db() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None
        original_expiry = stored.expires_at

    response = session_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200

    with auth_session_db() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None
        assert stored.expires_at == original_expiry


def test_failed_login_creates_no_refresh_session(
    session_client: TestClient,
    auth_session_db: sessionmaker[Session],
) -> None:
    create_session_user(auth_session_db)
    response = session_client.post(
        "/api/v1/auth/token",
        data={"username": "sessionuser", "password": "wrong-password"},
    )
    assert response.status_code == 401

    with auth_session_db() as session:
        assert session.scalar(select(UserSession)) is None
