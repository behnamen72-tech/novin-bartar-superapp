from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.access.permissions import (
    ACCESS_MANAGE,
    ACCESS_READ,
    AUDIT_READ,
    DOCUMENTS_MANAGE,
    DOCUMENTS_READ,
    ORGANIZATION_MANAGE,
    ORGANIZATION_READ,
    PEOPLE_MANAGE,
    PEOPLE_READ,
    USERS_MANAGE,
    USERS_READ,
)
from app.core.audit.models import AuditEvent
from app.core.identity.admin_schemas import UserPasswordResetRequest
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password, verify_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ALL_CORE_PERMISSIONS = (
    ORGANIZATION_READ,
    ORGANIZATION_MANAGE,
    PEOPLE_READ,
    PEOPLE_MANAGE,
    USERS_READ,
    USERS_MANAGE,
    ACCESS_READ,
    ACCESS_MANAGE,
    AUDIT_READ,
    DOCUMENTS_READ,
    DOCUMENTS_MANAGE,
)


@pytest.fixture
def write_db() -> Iterator[sessionmaker[Session]]:
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
def client(write_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = write_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def auth_headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _add_permission(session: Session, code: str) -> Permission:
    existing = session.scalar(select(Permission).where(Permission.code == code))
    if existing is not None:
        return existing
    permission = Permission(code=code, name=code, description=code)
    session.add(permission)
    session.flush()
    return permission


def _add_role(
    session: Session,
    *,
    code: str,
    permission_codes: tuple[str, ...],
    organization: Organization | None = None,
    is_system: bool = False,
) -> Role:
    role = Role(
        code=code,
        name=code,
        organization=organization,
        is_system=is_system,
    )
    session.add(role)
    session.flush()
    for code_value in permission_codes:
        role.permission_links.append(
            RolePermission(permission=_add_permission(session, code_value))
        )
    return role


def seed_super_admin(factory: sessionmaker[Session]):
    with factory() as session:
        holding = Organization(
            name="Holding",
            code=f"H-{uuid4()}",
            organization_type=OrganizationType.HOLDING,
        )
        company_a = Organization(
            name="Company A",
            code=f"A-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        branch_a = Organization(
            name="Branch A",
            code=f"BA-{uuid4()}",
            organization_type=OrganizationType.BRANCH,
            parent=company_a,
        )
        company_b = Organization(
            name="Company B",
            code=f"B-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        actor_person = Person(
            first_name="Root",
            last_name="Admin",
            email=f"root-{uuid4()}@example.test",
        )
        actor_relationship = PersonOrganizationRelationship(
            person=actor_person,
            organization=holding,
            relationship_code="administrator",
        )
        actor = User(
            person=actor_person,
            email=actor_person.email or "root@example.test",
            username=f"root-{uuid4()}",
            password_hash=hash_password("Root-password-123!"),
        )
        role = _add_role(
            session,
            code=f"super-{uuid4()}",
            permission_codes=ALL_CORE_PERMISSIONS,
            is_system=True,
        )
        assignment = UserRoleAssignment(
            user=actor,
            role=role,
            organization=holding,
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
        )
        session.add_all(
            [
                holding,
                company_a,
                branch_a,
                company_b,
                actor_person,
                actor_relationship,
                actor,
                assignment,
            ]
        )
        session.commit()
        return actor.id, role.id, assignment.id, holding.id, company_a.id, branch_a.id, company_b.id


def seed_person(factory: sessionmaker[Session], organization_id, *, label: str = "Target"):
    with factory() as session:
        organization = session.get(Organization, organization_id)
        assert organization is not None
        person = Person(
            first_name=label,
            last_name="Person",
            email=f"{label.lower()}-{uuid4()}@example.test",
        )
        relationship = PersonOrganizationRelationship(
            person=person,
            organization=organization,
            relationship_code="employee",
        )
        session.add_all([person, relationship])
        session.commit()
        return person.id, relationship.id


def test_organization_write_creates_audited_descendant(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, holding_id, _, _, _ = seed_super_admin(write_db)

    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(actor_id),
        json={
            "name": "New Company",
            "code": "new-company",
            "organization_type": "company",
            "parent_id": str(holding_id),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["code"] == "NEW-COMPANY"

    with write_db() as session:
        created = session.scalar(select(Organization).where(Organization.code == "NEW-COMPANY"))
        assert created is not None
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "organization.created",
                AuditEvent.resource_id == str(created.id),
            )
        )
        assert audit is not None
        assert audit.organization_id == created.id


def test_self_only_organization_manager_cannot_create_child(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    with write_db() as session:
        holding = Organization(name="Holding", code=f"H-{uuid4()}", organization_type=OrganizationType.HOLDING)
        person = Person(first_name="Self", last_name="Manager", email=f"self-{uuid4()}@test.local")
        user = User(person=person, email=person.email or "self@test.local", password_hash=hash_password("Self-password-123!"))
        role = _add_role(session, code=f"self-role-{uuid4()}", permission_codes=(ORGANIZATION_MANAGE,))
        session.add_all([
            holding,
            person,
            UserRoleAssignment(user=user, role=role, organization=holding, scope_mode=OrganizationScopeMode.SELF),
        ])
        session.commit()
        user_id, holding_id = user.id, holding.id

    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(user_id),
        json={"name": "Denied", "code": "DENIED-CHILD", "organization_type": "company", "parent_id": str(holding_id)},
    )
    assert response.status_code == 403
    with write_db() as session:
        assert session.scalar(select(Organization).where(Organization.code == "DENIED-CHILD")) is None


def test_organization_write_rolls_back_when_audit_fails(
    client: TestClient,
    write_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id, _, _, holding_id, _, _, _ = seed_super_admin(write_db)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("app.core.organization.service.record_audit_event", fail_audit)
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(actor_id),
        json={"name": "Rollback Co", "code": "ROLLBACK-CO", "organization_type": "company", "parent_id": str(holding_id)},
    )
    assert response.status_code == 500
    with write_db() as session:
        assert session.scalar(select(Organization).where(Organization.code == "ROLLBACK-CO")) is None


def test_parent_with_active_child_cannot_be_deactivated(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    response = client.patch(
        f"/api/v1/organizations/{company_a_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert response.status_code == 409


def test_person_create_and_relationship_are_audited(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    response = client.post(
        "/api/v1/people",
        headers=auth_headers(actor_id),
        json={
            "organization_id": str(company_a_id),
            "relationship_code": "employee",
            "first_name": "Ali",
            "last_name": "Test",
            "email": "ali@example.test",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["relationships"][0]["organization_id"] == str(company_a_id)
    with write_db() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "person.created",
                AuditEvent.resource_id == body["id"],
            )
        )
        assert event is not None


def test_shared_person_update_requires_manage_across_all_active_relationships(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    _, _, _, _, company_a_id, _, company_b_id = seed_super_admin(write_db)
    with write_db() as session:
        company_a = session.get(Organization, company_a_id)
        company_b = session.get(Organization, company_b_id)
        assert company_a and company_b
        actor_person = Person(first_name="A", last_name="Admin", email=f"a-{uuid4()}@test.local")
        actor = User(person=actor_person, email=actor_person.email or "a@test.local", password_hash=hash_password("Actor-password-123!"))
        actor_rel = PersonOrganizationRelationship(person=actor_person, organization=company_a, relationship_code="manager")
        actor_role = _add_role(session, code=f"pm-{uuid4()}", permission_codes=(PEOPLE_MANAGE,))
        target = Person(first_name="Shared", last_name="Person", email=f"shared-{uuid4()}@test.local")
        session.add_all([
            actor_person,
            actor,
            actor_rel,
            UserRoleAssignment(user=actor, role=actor_role, organization=company_a, scope_mode=OrganizationScopeMode.SELF),
            target,
            PersonOrganizationRelationship(person=target, organization=company_a, relationship_code="employee"),
            PersonOrganizationRelationship(person=target, organization=company_b, relationship_code="contractor"),
        ])
        session.commit()
        actor_id, target_id = actor.id, target.id

    response = client.patch(
        f"/api/v1/people/{target_id}",
        headers=auth_headers(actor_id),
        json={"first_name": "Changed"},
    )
    assert response.status_code == 403


def test_user_create_hashes_password_and_never_audits_plaintext(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    person_id, _ = seed_person(write_db, company_a_id, label="Login")
    password = "Initial-user-password-123!"
    response = client.post(
        "/api/v1/users",
        headers=auth_headers(actor_id),
        json={
            "person_id": str(person_id),
            "email": "new-user@example.test",
            "username": "new-user",
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    with write_db() as session:
        user = session.get(User, UUID(user_id))
        assert user is not None
        assert user.password_hash != password
        assert verify_password(password, user.password_hash)
        events = list(session.scalars(select(AuditEvent).where(AuditEvent.resource_id == str(user.id))).all())
        assert events
        serialized = repr([(event.before_state, event.after_state, event.event_metadata) for event in events])
        assert password not in serialized
        assert user.password_hash not in serialized


def test_identity_admin_cannot_mutate_user_with_permissions_actor_does_not_own(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    with write_db() as session:
        company = Organization(name="Company", code=f"C-{uuid4()}", organization_type=OrganizationType.COMPANY, parent=Organization(name="Holding", code=f"H-{uuid4()}", organization_type=OrganizationType.HOLDING))
        actor_person = Person(first_name="Limited", last_name="Admin", email=f"limited-{uuid4()}@test.local")
        actor = User(person=actor_person, email=actor_person.email or "limited@test.local", password_hash=hash_password("Limited-password-123!"))
        target_person = Person(first_name="Privileged", last_name="User", email=f"priv-{uuid4()}@test.local")
        target = User(person=target_person, email=target_person.email or "priv@test.local", password_hash=hash_password("Priv-password-123!"))
        actor_role = _add_role(session, code=f"limited-{uuid4()}", permission_codes=(USERS_MANAGE, ACCESS_MANAGE))
        target_role = _add_role(session, code=f"target-{uuid4()}", permission_codes=(DOCUMENTS_MANAGE,))
        session.add_all([
            company,
            actor_person,
            actor,
            target_person,
            target,
            PersonOrganizationRelationship(person=actor_person, organization=company, relationship_code="manager"),
            PersonOrganizationRelationship(person=target_person, organization=company, relationship_code="employee"),
            UserRoleAssignment(user=actor, role=actor_role, organization=company, scope_mode=OrganizationScopeMode.SELF),
            UserRoleAssignment(user=target, role=target_role, organization=company, scope_mode=OrganizationScopeMode.SELF),
        ])
        session.commit()
        actor_id, target_id = actor.id, target.id

    response = client.patch(
        f"/api/v1/users/{target_id}",
        headers=auth_headers(actor_id),
        json={"email": "hijack@example.test"},
    )
    assert response.status_code == 403


def test_custom_role_permission_grant_is_capability_bounded(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    created = client.post(
        "/api/v1/access/roles",
        headers=auth_headers(actor_id),
        json={"organization_id": str(company_a_id), "code": "company_operator", "name": "Company Operator"},
    )
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    granted = client.post(
        f"/api/v1/access/roles/{role_id}/permissions/{PEOPLE_READ}",
        headers=auth_headers(actor_id),
    )
    assert granted.status_code == 200, granted.text
    assert PEOPLE_READ in granted.json()["permissions"]

    with write_db() as session:
        company = session.get(Organization, company_a_id)
        assert company is not None
        limited_person = Person(first_name="Access", last_name="Manager", email=f"am-{uuid4()}@test.local")
        limited = User(person=limited_person, email=limited_person.email or "am@test.local", password_hash=hash_password("Access-password-123!"))
        limited_role = _add_role(session, code=f"access-only-{uuid4()}", permission_codes=(ACCESS_MANAGE, ACCESS_READ))
        session.add_all([
            limited_person,
            limited,
            PersonOrganizationRelationship(person=limited_person, organization=company, relationship_code="manager"),
            UserRoleAssignment(user=limited, role=limited_role, organization=company, scope_mode=OrganizationScopeMode.SELF),
        ])
        session.commit()
        limited_id = limited.id

    denied = client.post(
        f"/api/v1/access/roles/{role_id}/permissions/{DOCUMENTS_MANAGE}",
        headers=auth_headers(limited_id),
    )
    assert denied.status_code == 403


def test_system_role_definition_is_immutable_via_api(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, system_role_id, _, _, _, _, _ = seed_super_admin(write_db)
    response = client.patch(
        f"/api/v1/access/roles/{system_role_id}",
        headers=auth_headers(actor_id),
        json={"name": "Changed"},
    )
    assert response.status_code == 409


def test_role_assignment_is_scoped_and_audited(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    person_id, _ = seed_person(write_db, company_a_id, label="Assigned")
    user_response = client.post(
        "/api/v1/users",
        headers=auth_headers(actor_id),
        json={"person_id": str(person_id), "email": "assigned@example.test", "password": "Assigned-password-123!"},
    )
    assert user_response.status_code == 201, user_response.text
    target_user_id = user_response.json()["id"]

    role_response = client.post(
        "/api/v1/access/roles",
        headers=auth_headers(actor_id),
        json={"organization_id": str(company_a_id), "code": "reader_custom", "name": "Reader Custom"},
    )
    assert role_response.status_code == 201
    role_id = role_response.json()["id"]
    assert client.post(
        f"/api/v1/access/roles/{role_id}/permissions/{PEOPLE_READ}",
        headers=auth_headers(actor_id),
    ).status_code == 200

    assigned = client.post(
        "/api/v1/access/assignments",
        headers=auth_headers(actor_id),
        json={
            "user_id": target_user_id,
            "role_id": role_id,
            "organization_id": str(company_a_id),
            "scope_mode": "self",
        },
    )
    assert assigned.status_code == 201, assigned.text
    assignment_id = assigned.json()["id"]
    with write_db() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "role.assigned",
                AuditEvent.resource_id == assignment_id,
            )
        )
        assert event is not None


def test_descendant_scope_assignment_requires_actor_authority_in_descendants(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    _, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    with write_db() as session:
        company = session.get(Organization, company_a_id)
        assert company is not None
        actor_person = Person(first_name="Company", last_name="Admin", email=f"company-{uuid4()}@test.local")
        actor = User(person=actor_person, email=actor_person.email or "company@test.local", password_hash=hash_password("Company-password-123!"))
        target_person = Person(first_name="Target", last_name="User", email=f"target-{uuid4()}@test.local")
        target = User(person=target_person, email=target_person.email or "target@test.local", password_hash=hash_password("Target-password-123!"))
        actor_role = _add_role(session, code=f"self-manager-{uuid4()}", permission_codes=(ACCESS_MANAGE, PEOPLE_READ))
        custom_role = _add_role(session, code=f"owned-{uuid4()}", permission_codes=(PEOPLE_READ,), organization=company)
        session.add_all([
            actor_person,
            actor,
            target_person,
            target,
            PersonOrganizationRelationship(person=actor_person, organization=company, relationship_code="manager"),
            PersonOrganizationRelationship(person=target_person, organization=company, relationship_code="employee"),
            UserRoleAssignment(user=actor, role=actor_role, organization=company, scope_mode=OrganizationScopeMode.SELF),
        ])
        session.commit()
        actor_id, target_id, role_id = actor.id, target.id, custom_role.id

    response = client.post(
        "/api/v1/access/assignments",
        headers=auth_headers(actor_id),
        json={
            "user_id": str(target_id),
            "role_id": str(role_id),
            "organization_id": str(company_a_id),
            "scope_mode": "self_and_descendants",
        },
    )
    assert response.status_code == 403


def test_last_effective_access_manager_assignment_cannot_be_deactivated(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, assignment_id, _, _, _, _ = seed_super_admin(write_db)
    response = client.patch(
        f"/api/v1/access/assignments/{assignment_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert response.status_code == 409


def test_password_reset_audit_contains_no_secret_material(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    person_id, _ = seed_person(write_db, company_a_id, label="Reset")
    created = client.post(
        "/api/v1/users",
        headers=auth_headers(actor_id),
        json={"person_id": str(person_id), "email": "reset@example.test", "password": "Before-password-123!"},
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    new_password = "After-password-456!"
    reset_payload = UserPasswordResetRequest(new_password=new_password)
    assert new_password not in repr(reset_payload)
    response = client.post(
        f"/api/v1/users/{user_id}/password-reset",
        headers=auth_headers(actor_id),
        json={"new_password": new_password},
    )
    assert response.status_code == 204
    with write_db() as session:
        target = session.get(User, UUID(user_id))
        assert target is not None and verify_password(new_password, target.password_hash)
        events = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "user.password.reset",
                    AuditEvent.resource_id == str(user_id),
                )
            ).all()
        )
        assert events
        serialized = repr([(e.before_state, e.after_state, e.event_metadata) for e in events])
        assert new_password not in serialized
        assert target.password_hash not in serialized


def test_inactive_organization_can_be_reactivated_by_ancestor_descendant_scope_admin(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, branch_a_id, _ = seed_super_admin(write_db)
    # First deactivate the leaf branch.
    off = client.patch(
        f"/api/v1/organizations/{branch_a_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False

    on = client.patch(
        f"/api/v1/organizations/{branch_a_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": True},
    )
    assert on.status_code == 200, on.text
    assert on.json()["is_active"] is True
    assert on.json()["parent_id"] == str(company_a_id)


def test_people_manager_cannot_disable_person_linked_to_more_privileged_user(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    with write_db() as session:
        holding = Organization(name="Holding", code=f"H-{uuid4()}", organization_type=OrganizationType.HOLDING)
        company = Organization(name="Company", code=f"C-{uuid4()}", organization_type=OrganizationType.COMPANY, parent=holding)
        actor_person = Person(first_name="People", last_name="Manager", email=f"people-{uuid4()}@test.local")
        actor = User(person=actor_person, email=actor_person.email or "people@test.local", password_hash=hash_password("People-password-123!"))
        target_person = Person(first_name="Privileged", last_name="Person", email=f"privp-{uuid4()}@test.local")
        target_user = User(person=target_person, email=target_person.email or "privp@test.local", password_hash=hash_password("Privileged-password-123!"))
        actor_role = _add_role(session, code=f"people-manager-{uuid4()}", permission_codes=(PEOPLE_MANAGE, ACCESS_MANAGE))
        target_role = _add_role(session, code=f"priv-role-{uuid4()}", permission_codes=(DOCUMENTS_MANAGE,))
        session.add_all([
            holding,
            company,
            actor_person,
            actor,
            target_person,
            target_user,
            PersonOrganizationRelationship(person=actor_person, organization=company, relationship_code="manager"),
            PersonOrganizationRelationship(person=target_person, organization=company, relationship_code="employee"),
            UserRoleAssignment(user=actor, role=actor_role, organization=company, scope_mode=OrganizationScopeMode.SELF),
            UserRoleAssignment(user=target_user, role=target_role, organization=company, scope_mode=OrganizationScopeMode.SELF),
        ])
        session.commit()
        actor_id, target_person_id = actor.id, target_person.id

    response = client.patch(
        f"/api/v1/people/{target_person_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert response.status_code == 403
    with write_db() as session:
        target = session.get(Person, target_person_id)
        assert target is not None and target.is_active is True


def test_new_username_cannot_use_email_login_shape(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    person_id, _ = seed_person(write_db, company_a_id, label="Username")
    response = client.post(
        "/api/v1/users",
        headers=auth_headers(actor_id),
        json={
            "person_id": str(person_id),
            "email": "username-owner@example.test",
            "username": "looks@like-email.test",
            "password": "Username-password-123!",
        },
    )
    assert response.status_code == 422


def test_relationship_cannot_be_deactivated_while_access_is_rooted_there(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    person_id, relationship_id = seed_person(write_db, company_a_id, label="AccessRoot")
    user_response = client.post(
        "/api/v1/users",
        headers=auth_headers(actor_id),
        json={
            "person_id": str(person_id),
            "email": "access-root@example.test",
            "password": "Access-root-password-123!",
        },
    )
    assert user_response.status_code == 201
    role_response = client.post(
        "/api/v1/access/roles",
        headers=auth_headers(actor_id),
        json={
            "organization_id": str(company_a_id),
            "code": "access_root_reader",
            "name": "Access Root Reader",
        },
    )
    role_id = role_response.json()["id"]
    assert client.post(
        f"/api/v1/access/roles/{role_id}/permissions/{PEOPLE_READ}",
        headers=auth_headers(actor_id),
    ).status_code == 200
    assert client.post(
        "/api/v1/access/assignments",
        headers=auth_headers(actor_id),
        json={
            "user_id": user_response.json()["id"],
            "role_id": role_id,
            "organization_id": str(company_a_id),
            "scope_mode": "self",
        },
    ).status_code == 201

    response = client.patch(
        f"/api/v1/people/{person_id}/relationships/{relationship_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert response.status_code == 409


def test_assignment_reactivation_rechecks_person_relationship(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    person_id, relationship_id = seed_person(write_db, company_a_id, label="Reactivation")
    user_response = client.post(
        "/api/v1/users",
        headers=auth_headers(actor_id),
        json={
            "person_id": str(person_id),
            "email": "reactivation@example.test",
            "password": "Reactivation-password-123!",
        },
    )
    role_response = client.post(
        "/api/v1/access/roles",
        headers=auth_headers(actor_id),
        json={
            "organization_id": str(company_a_id),
            "code": "reactivation_reader",
            "name": "Reactivation Reader",
        },
    )
    role_id = role_response.json()["id"]
    assert client.post(
        f"/api/v1/access/roles/{role_id}/permissions/{PEOPLE_READ}",
        headers=auth_headers(actor_id),
    ).status_code == 200
    assigned = client.post(
        "/api/v1/access/assignments",
        headers=auth_headers(actor_id),
        json={
            "user_id": user_response.json()["id"],
            "role_id": role_id,
            "organization_id": str(company_a_id),
            "scope_mode": "self",
        },
    )
    assert assigned.status_code == 201
    assignment_id = assigned.json()["id"]
    assert client.patch(
        f"/api/v1/access/assignments/{assignment_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    ).status_code == 200
    assert client.patch(
        f"/api/v1/people/{person_id}/relationships/{relationship_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    ).status_code == 200

    reactivation = client.patch(
        f"/api/v1/access/assignments/{assignment_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": True},
    )
    assert reactivation.status_code == 409


def test_role_permission_revoke_is_audited(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, company_a_id, _, _ = seed_super_admin(write_db)
    created = client.post(
        "/api/v1/access/roles",
        headers=auth_headers(actor_id),
        json={
            "organization_id": str(company_a_id),
            "code": "revoke_test",
            "name": "Revoke Test",
        },
    )
    role_id = created.json()["id"]
    assert client.post(
        f"/api/v1/access/roles/{role_id}/permissions/{PEOPLE_READ}",
        headers=auth_headers(actor_id),
    ).status_code == 200
    revoked = client.delete(
        f"/api/v1/access/roles/{role_id}/permissions/{PEOPLE_READ}",
        headers=auth_headers(actor_id),
    )
    assert revoked.status_code == 200, revoked.text
    assert PEOPLE_READ not in revoked.json()["permissions"]
    with write_db() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "permission.revoked",
                AuditEvent.resource_id == role_id,
            )
        )
        assert event is not None


def test_organization_management_listing_includes_recoverable_inactive_descendant(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, _, branch_a_id, _ = seed_super_admin(write_db)

    deactivate = client.patch(
        f"/api/v1/organizations/{branch_a_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert deactivate.status_code == 200, deactivate.text

    default_list = client.get(
        "/api/v1/organizations",
        headers=auth_headers(actor_id),
    )
    assert default_list.status_code == 200, default_list.text
    assert str(branch_a_id) not in {item["id"] for item in default_list.json()}

    management_list = client.get(
        "/api/v1/organizations?include_inactive=true",
        headers=auth_headers(actor_id),
    )
    assert management_list.status_code == 200, management_list.text
    by_id = {item["id"]: item for item in management_list.json()}
    assert str(branch_a_id) in by_id
    assert by_id[str(branch_a_id)]["is_active"] is False


def test_root_holding_status_cannot_be_changed_through_api(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, holding_id, _, _, _ = seed_super_admin(write_db)

    response = client.patch(
        f"/api/v1/organizations/{holding_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert response.status_code == 400, response.text

    with write_db() as session:
        holding = session.get(Organization, holding_id)
        assert holding is not None
        assert holding.is_active is True


def test_root_holding_status_still_requires_manage_permission_before_validation(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    _, _, _, holding_id, _, _, _ = seed_super_admin(write_db)
    with write_db() as session:
        person = Person(
            first_name="Read",
            last_name="Only",
            email=f"readonly-{uuid4()}@example.test",
        )
        user = User(
            person=person,
            email=person.email or "readonly@example.test",
            password_hash=hash_password("Readonly-password-123!"),
        )
        role = _add_role(
            session,
            code=f"readonly-{uuid4()}",
            permission_codes=(ORGANIZATION_READ,),
        )
        holding = session.get(Organization, holding_id)
        assert holding is not None
        session.add_all(
            [
                person,
                user,
                UserRoleAssignment(
                    user=user,
                    role=role,
                    organization=holding,
                    scope_mode=OrganizationScopeMode.SELF,
                ),
            ]
        )
        session.commit()
        user_id = user.id

    response = client.patch(
        f"/api/v1/organizations/{holding_id}/status",
        headers=auth_headers(user_id),
        json={"is_active": False},
    )
    assert response.status_code == 403, response.text


def test_actor_cannot_deactivate_own_person(
    client: TestClient,
    write_db: sessionmaker[Session],
) -> None:
    actor_id, _, _, _, _, _, _ = seed_super_admin(write_db)
    with write_db() as session:
        actor = session.get(User, actor_id)
        assert actor is not None
        actor_person_id = actor.person_id

    response = client.patch(
        f"/api/v1/people/{actor_person_id}/status",
        headers=auth_headers(actor_id),
        json={"is_active": False},
    )
    assert response.status_code == 409, response.text

    with write_db() as session:
        person = session.get(Person, actor_person_id)
        assert person is not None
        assert person.is_active is True
