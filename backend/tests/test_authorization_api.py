from collections.abc import Iterator

import pytest
from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def access_db() -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(access_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = access_db()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def seed(access_db: sessionmaker[Session]):
    with access_db() as session:
        holding = Organization(name="Holding", code="H-API", organization_type=OrganizationType.HOLDING)
        company_a = Organization(name="A", code="A-API", organization_type=OrganizationType.COMPANY, parent=holding)
        company_b = Organization(name="B", code="B-API", organization_type=OrganizationType.COMPANY, parent=holding)
        person = Person(first_name="A", last_name="User", email="a@x.test")
        user = User(person=person, email="a@x.test", username="auser", password_hash=hash_password("Strong-password-123!"))
        permission = Permission(code="people.read", name="Read people")
        role = Role(code="reader", name="Reader")
        role.permission_links.append(RolePermission(permission=permission))
        assignment = UserRoleAssignment(user=user, role=role, organization=company_a, scope_mode=OrganizationScopeMode.SELF)
        session.add_all([holding, company_a, company_b, person, user, permission, role, assignment])
        session.commit()
        return user.id, company_a.id, company_b.id


def test_access_endpoints_require_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/access/me")
    assert response.status_code == 401


def test_permission_check_is_scoped_to_organization(client: TestClient, access_db: sessionmaker[Session]) -> None:
    user_id, company_a_id, company_b_id = seed(access_db)
    token = create_access_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    allowed = client.get(f"/api/v1/access/organizations/{company_a_id}/permissions/people.read", headers=headers)
    denied = client.get(f"/api/v1/access/organizations/{company_b_id}/permissions/people.read", headers=headers)

    assert allowed.status_code == 200
    assert allowed.json()["allowed"] is True
    assert denied.status_code == 200
    assert denied.json()["allowed"] is False


def test_my_access_does_not_expose_other_users(client: TestClient, access_db: sessionmaker[Session]) -> None:
    user_id, company_a_id, _ = seed(access_db)
    token = create_access_token(user_id)
    response = client.get("/api/v1/access/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["organization_id"] == str(company_a_id)
    assert body[0]["permissions"] == ["people.read"]
