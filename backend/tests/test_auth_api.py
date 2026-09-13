from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.identity.models import User
from app.core.identity.security import hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def auth_db() -> Iterator[sessionmaker[Session]]:
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
def client(auth_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = auth_db()
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


def create_login_user(
    auth_db: sessionmaker[Session],
    *,
    active: bool = True,
    person_active: bool = True,
) -> User:
    with auth_db() as session:
        holding = Organization(
            name="Novin Bartar",
            code="NOVIN-AUTH",
            organization_type=OrganizationType.HOLDING,
        )
        company = Organization(
            name="Enferadi Market",
            code="ENFERADI-AUTH",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        person = Person(
            first_name="Auth",
            last_name="User",
            email="auth.person@example.com",
            is_active=person_active,
        )
        relationship = PersonOrganizationRelationship(
            person=person,
            organization=company,
            relationship_code="employee",
        )
        user = User(
            person=person,
            email="login@example.com",
            username="authuser",
            password_hash=hash_password("Correct-password-123!"),
            is_active=active,
        )
        session.add_all([holding, company, person, relationship, user])
        session.commit()
        session.refresh(user)
        return user


def test_login_and_me_flow(
    client: TestClient,
    auth_db: sessionmaker[Session],
) -> None:
    user = create_login_user(auth_db)

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "LOGIN@EXAMPLE.COM",
            "password": "Correct-password-123!",
        },
    )

    assert login_response.status_code == 200
    body = login_response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )

    assert me_response.status_code == 200
    me = me_response.json()
    assert me["id"] == str(user.id)
    assert me["email"] == "login@example.com"
    assert me["username"] == "authuser"
    assert "password_hash" not in me


def test_login_by_username(
    client: TestClient,
    auth_db: sessionmaker[Session],
) -> None:
    create_login_user(auth_db)

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "AUTHUSER",
            "password": "Correct-password-123!",
        },
    )

    assert response.status_code == 200


def test_wrong_password_is_rejected(
    client: TestClient,
    auth_db: sessionmaker[Session],
) -> None:
    create_login_user(auth_db)

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "authuser",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


def test_unknown_user_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "missing-user",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


def test_inactive_user_is_rejected(
    client: TestClient,
    auth_db: sessionmaker[Session],
) -> None:
    create_login_user(auth_db, active=False)

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "authuser",
            "password": "Correct-password-123!",
        },
    )

    assert response.status_code == 401


def test_inactive_person_is_rejected(
    client: TestClient,
    auth_db: sessionmaker[Session],
) -> None:
    create_login_user(auth_db, person_active=False)

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "authuser",
            "password": "Correct-password-123!",
        },
    )

    assert response.status_code == 401


def test_me_requires_valid_bearer_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
