from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.audit.events import AuditIntegrityError
from app.core.audit.models import AuditEvent
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def audit_db() -> Iterator[sessionmaker[Session]]:
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
def client(audit_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = audit_db()
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


def seed_audit_case(
    audit_db: sessionmaker[Session],
    *,
    grant_audit: bool = True,
) -> tuple[User, Organization, Organization]:
    with audit_db() as session:
        holding = Organization(
            name="Holding",
            code=f"HOLD-{uuid4()}",
            organization_type=OrganizationType.HOLDING,
        )
        company_a = Organization(
            name="Company A",
            code=f"A-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        company_b = Organization(
            name="Company B",
            code=f"B-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        person = Person(
            first_name="Audit",
            last_name="Admin",
            email=f"audit-{uuid4()}@example.com",
        )
        session.add(
            PersonOrganizationRelationship(
                person=person,
                organization=company_a,
                relationship_code="manager",
            )
        )
        user = User(
            person=person,
            email=person.email or "audit@example.com",
            username=f"audit-{uuid4()}",
            password_hash=hash_password("Audit-password-123!"),
        )

        permission = Permission(
            code=f"audit.read.{uuid4()}" if not grant_audit else "audit.read",
            name="Audit read",
            description="Audit read",
        )
        role = Role(code=f"audit-role-{uuid4()}", name="Audit Role")

        session.add_all([holding, company_a, company_b, person, user, permission, role])
        session.flush()

        session.add(RolePermission(role=role, permission=permission))
        session.add(
            UserRoleAssignment(
                user=user,
                role=role,
                organization=company_a,
                scope_mode=OrganizationScopeMode.SELF,
            )
        )
        session.commit()

        return user, company_a, company_b


def test_audit_payload_redacts_sensitive_values(
    audit_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_audit_case(audit_db)

    with audit_db() as session:
        user_db = session.get(User, user.id)
        assert user_db is not None

        event = record_audit_event(
            session,
            actor=user_db,
            organization_id=company_a.id,
            action="update",
            resource_type="user",
            resource_id=user.id,
            after_state={
                "email": "new@example.com",
                "password_hash": "$argon2-secret",
                "nested": {
                    "access_token": "abc123",
                    "safe": "visible",
                },
            },
        )
        session.commit()
        session.refresh(event)

        assert event.after_state is not None
        assert event.after_state["password_hash"] == "[REDACTED]"
        nested = event.after_state["nested"]
        assert isinstance(nested, dict)
        assert nested["access_token"] == "[REDACTED]"
        assert nested["safe"] == "visible"


def test_audit_event_cannot_be_updated_or_deleted(
    audit_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_audit_case(audit_db)

    with audit_db() as session:
        user_db = session.get(User, user.id)
        assert user_db is not None
        event = record_audit_event(
            session,
            actor=user_db,
            organization_id=company_a.id,
            action="create",
            resource_type="person",
            resource_id=uuid4(),
        )
        session.commit()
        event_id = event.id

    with audit_db() as session:
        event = session.get(AuditEvent, event_id)
        assert event is not None
        event.action = "tampered"
        with pytest.raises(AuditIntegrityError):
            session.flush()
        session.rollback()

    with audit_db() as session:
        event = session.get(AuditEvent, event_id)
        assert event is not None
        session.delete(event)
        with pytest.raises(AuditIntegrityError):
            session.flush()


def test_audit_api_filters_by_organization_scope(
    client: TestClient,
    audit_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_audit_case(audit_db)

    with audit_db() as session:
        user_db = session.get(User, user.id)
        assert user_db is not None
        record_audit_event(
            session,
            actor=user_db,
            organization_id=company_a.id,
            action="update",
            resource_type="person",
            resource_id="visible",
        )
        record_audit_event(
            session,
            actor=user_db,
            organization_id=company_b.id,
            action="update",
            resource_type="person",
            resource_id="hidden",
        )
        record_audit_event(
            session,
            actor=None,
            organization_id=None,
            action="system.global",
            resource_type="system",
            resource_id="global",
        )
        session.commit()

    token = create_access_token(user.id)
    response = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    resource_ids = {item["resource_id"] for item in response.json()}
    assert "visible" in resource_ids
    assert "hidden" not in resource_ids
    assert "global" not in resource_ids


def test_audit_api_rejects_explicit_out_of_scope_organization(
    client: TestClient,
    audit_db: sessionmaker[Session],
) -> None:
    user, _, company_b = seed_audit_case(audit_db)

    token = create_access_token(user.id)
    response = client.get(
        f"/api/v1/audit?organization_id={company_b.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_user_without_audit_permission_sees_no_events(
    client: TestClient,
    audit_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_audit_case(audit_db, grant_audit=False)

    with audit_db() as session:
        user_db = session.get(User, user.id)
        assert user_db is not None
        record_audit_event(
            session,
            actor=user_db,
            organization_id=company_a.id,
            action="update",
            resource_type="person",
            resource_id="not-visible",
        )
        session.commit()

    token = create_access_token(user.id)
    response = client.get(
        "/api/v1/audit",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == []
