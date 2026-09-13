from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def core_db() -> Iterator[sessionmaker[Session]]:
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
def client(core_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = core_db()
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


def seed_scope_case(core_db: sessionmaker[Session]) -> tuple[User, Organization, Organization]:
    with core_db() as session:
        holding = Organization(
            name="Holding",
            code="HOLDING-CORE",
            organization_type=OrganizationType.HOLDING,
        )
        company_a = Organization(
            name="Company A",
            code="COMPANY-A-CORE",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        branch_a = Organization(
            name="Branch A",
            code="BRANCH-A-CORE",
            organization_type=OrganizationType.BRANCH,
            parent=company_a,
        )
        company_b = Organization(
            name="Company B",
            code="COMPANY-B-CORE",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )

        admin_person = Person(
            first_name="Admin",
            last_name="A",
            email="admin-a@example.com",
        )
        session.add(
            PersonOrganizationRelationship(
                person=admin_person,
                organization=company_a,
                relationship_code="manager",
            )
        )
        admin_user = User(
            person=admin_person,
            email="admin-a@example.com",
            username="admin-a",
            password_hash=hash_password("Admin-password-123!"),
        )

        person_a = Person(
            first_name="Visible",
            last_name="Person",
            email="visible@example.com",
        )
        session.add(
            PersonOrganizationRelationship(
                person=person_a,
                organization=branch_a,
                relationship_code="employee",
            )
        )
        visible_user = User(
            person=person_a,
            email="visible-user@example.com",
            username="visible-user",
            password_hash=hash_password("Visible-password-123!"),
        )

        person_b = Person(
            first_name="Hidden",
            last_name="Person",
            email="hidden@example.com",
        )
        session.add(
            PersonOrganizationRelationship(
                person=person_b,
                organization=company_b,
                relationship_code="employee",
            )
        )
        hidden_user = User(
            person=person_b,
            email="hidden-user@example.com",
            username="hidden-user",
            password_hash=hash_password("Hidden-password-123!"),
        )

        permissions = []
        for code in (
            "organization.read",
            "people.read",
            "users.read",
            "access.read",
        ):
            permission = Permission(
                code=code,
                name=code,
                description=code,
            )
            session.add(permission)
            permissions.append(permission)

        role = Role(code="reader-a", name="Reader A")
        session.add_all(
            [
                holding,
                company_a,
                branch_a,
                company_b,
                admin_person,
                admin_user,
                person_a,
                visible_user,
                person_b,
                hidden_user,
                role,
            ]
        )
        session.flush()

        for permission in permissions:
            session.add(RolePermission(role=role, permission=permission))

        assignment = UserRoleAssignment(
            user=admin_user,
            role=role,
            organization=company_a,
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
        )
        visible_assignment = UserRoleAssignment(
            user=visible_user,
            role=role,
            organization=branch_a,
            scope_mode=OrganizationScopeMode.SELF,
        )
        hidden_assignment = UserRoleAssignment(
            user=hidden_user,
            role=role,
            organization=company_b,
            scope_mode=OrganizationScopeMode.SELF,
        )

        session.add_all(
            [
                assignment,
                visible_assignment,
                hidden_assignment,
            ]
        )
        session.commit()
        session.refresh(admin_user)
        session.refresh(company_a)
        session.refresh(company_b)
        return admin_user, company_a, company_b


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def test_organizations_are_scope_filtered(
    client: TestClient,
    core_db: sessionmaker[Session],
) -> None:
    user, _, _ = seed_scope_case(core_db)

    response = client.get("/api/v1/organizations", headers=auth_headers(user))

    assert response.status_code == 200
    codes = {item["code"] for item in response.json()}
    assert codes == {"COMPANY-A-CORE", "BRANCH-A-CORE"}


def test_people_and_users_do_not_leak_sibling_company(
    client: TestClient,
    core_db: sessionmaker[Session],
) -> None:
    user, _, _ = seed_scope_case(core_db)

    people_response = client.get("/api/v1/people", headers=auth_headers(user))
    users_response = client.get("/api/v1/users", headers=auth_headers(user))

    assert people_response.status_code == 200
    assert users_response.status_code == 200

    people_emails = {item["email"] for item in people_response.json()}
    user_emails = {item["email"] for item in users_response.json()}

    assert "visible@example.com" in people_emails
    assert "hidden@example.com" not in people_emails
    assert "visible-user@example.com" in user_emails
    assert "hidden-user@example.com" not in user_emails


def test_access_overview_is_scope_filtered(
    client: TestClient,
    core_db: sessionmaker[Session],
) -> None:
    user, _, _ = seed_scope_case(core_db)

    response = client.get("/api/v1/access/overview", headers=auth_headers(user))

    assert response.status_code == 200
    emails = {item["user_email"] for item in response.json()}
    assert "admin-a@example.com" in emails
    assert "visible-user@example.com" in emails
    assert "hidden-user@example.com" not in emails
