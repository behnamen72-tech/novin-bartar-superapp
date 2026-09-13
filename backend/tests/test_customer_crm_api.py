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
from app.core.audit.models import AuditEvent
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.customers.models import CustomerCRMRecord
from app.modules.customers.permissions import (
    CRM_CUSTOMER_ASSIGN,
    CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,
    CRM_CUSTOMER_MANAGE,
    CRM_CUSTOMER_NOTES_MANAGE,
    CRM_CUSTOMER_NOTES_READ,
    CRM_CUSTOMER_READ,
    CRM_CUSTOMER_TAGS_MANAGE,
)
from app.modules.customers.schemas import CommerceCustomerValidationResult
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ALL_CRM_PERMISSIONS = (
    CRM_CUSTOMER_READ,
    CRM_CUSTOMER_MANAGE,
    CRM_CUSTOMER_NOTES_READ,
    CRM_CUSTOMER_NOTES_MANAGE,
    CRM_CUSTOMER_ASSIGN,
    CRM_CUSTOMER_TAGS_MANAGE,
    CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,
)


@pytest.fixture
def crm_db() -> Iterator[sessionmaker[Session]]:
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
def client(crm_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = crm_db()
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


def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _permission(session: Session, code: str) -> Permission:
    existing = session.scalar(select(Permission).where(Permission.code == code))
    if existing is not None:
        return existing
    permission = Permission(code=code, name=code, description=code)
    session.add(permission)
    session.flush()
    return permission


def _seed_user(
    session: Session,
    *,
    organization: Organization,
    permission_codes: tuple[str, ...],
    label: str,
    scope_mode: OrganizationScopeMode = OrganizationScopeMode.SELF,
) -> User:
    person = Person(
        first_name=label,
        last_name="User",
        email=f"{label.lower()}-{uuid4()}@test.local",
    )
    session.add(person)
    session.flush()
    session.add(
        PersonOrganizationRelationship(
            person=person,
            organization=organization,
            relationship_code="employee",
        )
    )
    user = User(
        person=person,
        email=person.email or f"{uuid4()}@test.local",
        username=f"{label.lower()}-{uuid4()}",
        password_hash=hash_password("CRM-Test-Password-123!"),
    )
    role = Role(code=f"crm-role-{uuid4()}", name="CRM role", organization=organization)
    session.add_all([user, role])
    session.flush()
    for code in permission_codes:
        role.permission_links.append(RolePermission(permission=_permission(session, code)))
    session.add(
        UserRoleAssignment(
            user=user,
            role=role,
            organization=organization,
            scope_mode=scope_mode,
        )
    )
    session.flush()
    return user


def _seed_tree(factory: sessionmaker[Session]) -> dict[str, UUID]:
    with factory() as session:
        holding = Organization(
            name="Holding",
            code=f"H-{uuid4()}",
            organization_type=OrganizationType.HOLDING,
        )
        branch_a = Organization(
            name="Company A",
            code=f"A-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        branch_b = Organization(
            name="Company B",
            code=f"B-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        session.add_all([holding, branch_a, branch_b])
        session.flush()
        admin = _seed_user(
            session,
            organization=holding,
            permission_codes=ALL_CRM_PERMISSIONS,
            label="Admin",
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
        )
        manager_a = _seed_user(
            session,
            organization=branch_a,
            permission_codes=ALL_CRM_PERMISSIONS,
            label="ManagerA",
        )
        reader_a = _seed_user(
            session,
            organization=branch_a,
            permission_codes=(CRM_CUSTOMER_READ,),
            label="ReaderA",
        )
        manager_b = _seed_user(
            session,
            organization=branch_b,
            permission_codes=ALL_CRM_PERMISSIONS,
            label="ManagerB",
        )
        no_crm = _seed_user(
            session,
            organization=branch_a,
            permission_codes=(),
            label="NoCRM",
        )
        session.commit()
        return {
            "holding": holding.id,
            "branch_a": branch_a.id,
            "branch_b": branch_b.id,
            "admin": admin.id,
            "manager_a": manager_a.id,
            "reader_a": reader_a.id,
            "manager_b": manager_b.id,
            "no_crm": no_crm.id,
        }


def _allow_commerce(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate(ref: str, *, organization_id: UUID) -> CommerceCustomerValidationResult:
        del organization_id
        return CommerceCustomerValidationResult(exists=not ref.startswith("missing"))

    monkeypatch.setattr(
        "app.modules.customers.service.validate_commerce_customer_reference",
        fake_validate,
    )


def _create_customer(
    client: TestClient,
    actor_id: UUID,
    organization_id: UUID,
    *,
    ref: str = "cus_shared_001",
    label: str = "مشتری آزمایشی",
) -> dict:
    response = client.post(
        "/api/v1/crm/customers",
        headers=headers(actor_id),
        json={
            "organization_id": str(organization_id),
            "commerce_customer_ref": ref,
            "customer_type": "individual",
            "commercial_status": "prospect",
            "source": "manual",
            "display_label": label,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_customer_reference_is_external_org_scoped_and_db_unique(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)

    first = _create_customer(client, ids["admin"], ids["branch_a"])
    assert first["commerce_customer_ref"] == "cus_shared_001"
    assert first["version"] == 1

    duplicate = client.post(
        "/api/v1/crm/customers",
        headers=headers(ids["admin"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "commerce_customer_ref": "cus_shared_001",
            "display_label": "duplicate",
        },
    )
    assert duplicate.status_code == 409

    # Same external customer may have independent CRM metadata in another organization.
    second = _create_customer(client, ids["admin"], ids["branch_b"], label="مشتری شعبه ب")
    assert second["id"] != first["id"]

    with crm_db() as session:
        rows = session.scalars(
            select(CustomerCRMRecord).where(CustomerCRMRecord.commerce_customer_ref == "cus_shared_001")
        ).all()
        assert {row.organization_id for row in rows} == {ids["branch_a"], ids["branch_b"]}


def test_cross_org_direct_resource_access_is_hidden(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(client, ids["manager_a"], ids["branch_a"], ref="cus_a")

    response = client.get(
        f"/api/v1/crm/customers/{customer['id']}",
        headers=headers(ids["manager_b"]),
    )
    assert response.status_code == 404

    update = client.patch(
        f"/api/v1/crm/customers/{customer['id']}",
        headers=headers(ids["manager_b"]),
        json={"expected_version": 1, "display_label": "leak attempt"},
    )
    assert update.status_code == 404


def test_note_body_never_enters_audit_and_note_version_is_enforced(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(client, ids["manager_a"], ids["branch_a"], ref="cus_note")
    secret_marker = "6037999999999999 CVV 123 SECRET-NOTE-MARKER"

    created = client.post(
        f"/api/v1/crm/customers/{customer['id']}/notes",
        headers=headers(ids["manager_a"]),
        json={"body": secret_marker},
    )
    assert created.status_code == 201, created.text
    note = created.json()
    assert note["body"] == secret_marker

    updated = client.patch(
        f"/api/v1/crm/customers/{customer['id']}/notes/{note['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "body": "updated safe body"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = client.patch(
        f"/api/v1/crm/customers/{customer['id']}/notes/{note['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "body": "stale overwrite"},
    )
    assert stale.status_code == 409

    with crm_db() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.resource_type == "customer_note")
        ).all()
        assert len(events) == 2
        serialized = " ".join(
            str((event.before_state, event.after_state, event.event_metadata)) for event in events
        )
        assert secret_marker not in serialized
        assert "updated safe body" not in serialized


def test_assignment_requires_valid_crm_context_and_does_not_create_access(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(client, ids["manager_a"], ids["branch_a"], ref="cus_assign")

    invalid = client.post(
        f"/api/v1/crm/customers/{customer['id']}/assign",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "assigned_owner_user_id": str(ids["no_crm"])},
    )
    assert invalid.status_code == 422

    valid = client.post(
        f"/api/v1/crm/customers/{customer['id']}/assign",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "assigned_owner_user_id": str(ids["reader_a"])},
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["assigned_owner_user_id"] == str(ids["reader_a"])

    # The unrelated no-CRM user still cannot read simply because assignment APIs exist.
    denied = client.get(
        f"/api/v1/crm/customers/{customer['id']}",
        headers=headers(ids["no_crm"]),
    )
    assert denied.status_code == 404


def test_search_reuses_crm_acl_before_limit(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    _create_customer(
        client,
        ids["manager_a"],
        ids["branch_a"],
        ref="cus_alpha_a",
        label="Alpha Customer A",
    )
    _create_customer(
        client,
        ids["manager_b"],
        ids["branch_b"],
        ref="cus_alpha_b",
        label="Alpha Customer B",
    )

    a_search = client.get(
        "/api/v1/search?q=Alpha&entity_type=customer&limit_per_type=20",
        headers=headers(ids["reader_a"]),
    )
    assert a_search.status_code == 200, a_search.text
    assert [item["title"] for item in a_search.json()["results"]] == ["Alpha Customer A"]

    admin_search = client.get(
        "/api/v1/search?q=Alpha&entity_type=customer&limit_per_type=20",
        headers=headers(ids["admin"]),
    )
    assert admin_search.status_code == 200
    assert {item["title"] for item in admin_search.json()["results"]} == {
        "Alpha Customer A",
        "Alpha Customer B",
    }


def test_commerce_validation_failure_and_outage_are_fail_closed(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = _seed_tree(crm_db)
    _allow_commerce(monkeypatch)
    missing = client.post(
        "/api/v1/crm/customers",
        headers=headers(ids["manager_a"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "commerce_customer_ref": "missing-customer",
            "display_label": "Missing",
        },
    )
    assert missing.status_code == 422

    from app.modules.customers.integration import CommerceIntegrationUnavailableError

    def unavailable(ref: str, *, organization_id: UUID):
        del ref, organization_id
        raise CommerceIntegrationUnavailableError("offline")

    monkeypatch.setattr(
        "app.modules.customers.service.validate_commerce_customer_reference",
        unavailable,
    )
    response = client.post(
        "/api/v1/crm/customers",
        headers=headers(ids["manager_a"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "commerce_customer_ref": "cus_offline",
            "display_label": "Offline",
        },
    )
    assert response.status_code == 503


def test_customer_and_note_optimistic_concurrency_and_text_limits(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(client, ids["manager_a"], ids["branch_a"], ref="cus_version")

    update = client.patch(
        f"/api/v1/crm/customers/{customer['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "commercial_status": "active"},
    )
    assert update.status_code == 200
    assert update.json()["version"] == 2

    stale = client.patch(
        f"/api/v1/crm/customers/{customer['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "commercial_status": "inactive"},
    )
    assert stale.status_code == 409

    too_long = client.post(
        f"/api/v1/crm/customers/{customer['id']}/notes",
        headers=headers(ids["manager_a"]),
        json={"body": "x" * 4001},
    )
    assert too_long.status_code == 422


def test_commerce_activity_has_separate_permission(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(client, ids["manager_a"], ids["branch_a"], ref="cus_activity")

    denied = client.get(
        f"/api/v1/crm/customers/{customer['id']}/commerce-activity",
        headers=headers(ids["reader_a"]),
    )
    assert denied.status_code == 404

    def fake_activity(ref: str, *, organization_id: UUID):
        from app.modules.customers.schemas import CommerceActivityProjection

        assert ref == "cus_activity"
        assert organization_id == ids["branch_a"]
        return CommerceActivityProjection(orders=[])

    monkeypatch.setattr(
        "app.modules.customers.service.fetch_commerce_customer_activity",
        fake_activity,
    )
    allowed = client.get(
        f"/api/v1/crm/customers/{customer['id']}/commerce-activity",
        headers=headers(ids["manager_a"]),
    )
    assert allowed.status_code == 200
    assert allowed.json()["orders"] == []


def test_invalid_commerce_reference_and_archived_create_are_rejected(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)

    invalid_ref = client.post(
        "/api/v1/crm/customers",
        headers=headers(ids["manager_a"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "commerce_customer_ref": "cus/unsafe?ref=1",
            "display_label": "Unsafe ref",
        },
    )
    assert invalid_ref.status_code == 422

    unicode_ref = client.post(
        "/api/v1/crm/customers",
        headers=headers(ids["manager_a"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "commerce_customer_ref": "cus_مشتری",
            "display_label": "Unicode external ref",
        },
    )
    assert unicode_ref.status_code == 422

    archived = client.post(
        "/api/v1/crm/customers",
        headers=headers(ids["manager_a"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "commerce_customer_ref": "cus_archived_create",
            "commercial_status": "archived",
            "display_label": "Archived on create",
        },
    )
    assert archived.status_code == 422


def test_archive_restore_keeps_lifecycle_state_consistent(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(
        client,
        ids["manager_a"],
        ids["branch_a"],
        ref="cus_lifecycle",
    )

    archived = client.post(
        f"/api/v1/crm/customers/{customer['id']}/status",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "is_active": False},
    )
    assert archived.status_code == 200, archived.text
    archived_body = archived.json()
    assert archived_body["is_active"] is False
    assert archived_body["commercial_status"] == "archived"
    assert archived_body["version"] == 2

    restored = client.post(
        f"/api/v1/crm/customers/{customer['id']}/status",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 2, "is_active": True},
    )
    assert restored.status_code == 200, restored.text
    restored_body = restored.json()
    assert restored_body["is_active"] is True
    assert restored_body["commercial_status"] == "inactive"
    assert restored_body["version"] == 3


def test_specialized_note_and_activity_permissions_still_require_base_read(
    client: TestClient,
    crm_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_commerce(monkeypatch)
    ids = _seed_tree(crm_db)
    customer = _create_customer(
        client,
        ids["manager_a"],
        ids["branch_a"],
        ref="cus_specialized_permissions",
    )

    with crm_db() as session:
        branch_a = session.get(Organization, ids["branch_a"])
        assert branch_a is not None
        notes_only = _seed_user(
            session,
            organization=branch_a,
            permission_codes=(CRM_CUSTOMER_NOTES_READ, CRM_CUSTOMER_NOTES_MANAGE),
            label="NotesOnly",
        )
        activity_only = _seed_user(
            session,
            organization=branch_a,
            permission_codes=(CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,),
            label="ActivityOnly",
        )
        session.commit()
        notes_only_id = notes_only.id
        activity_only_id = activity_only.id

    note = client.post(
        f"/api/v1/crm/customers/{customer['id']}/notes",
        headers=headers(notes_only_id),
        json={"body": "should not be allowed without base read"},
    )
    assert note.status_code == 404

    activity = client.get(
        f"/api/v1/crm/customers/{customer['id']}/commerce-activity",
        headers=headers(activity_only_id),
    )
    assert activity.status_code == 404


def test_tag_free_text_is_not_copied_into_audit_payload(
    client: TestClient,
    crm_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(crm_db)
    sensitive_tag = "VIP-SECRET-603799"
    created = client.post(
        "/api/v1/crm/customer-tags",
        headers=headers(ids["manager_a"]),
        json={"organization_id": str(ids["branch_a"]), "name": sensitive_tag},
    )
    assert created.status_code == 201, created.text

    with crm_db() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.resource_type == "customer_tag")
        ).all()
        assert len(events) == 1
        serialized = str(
            (events[0].before_state, events[0].after_state, events[0].event_metadata)
        )
        assert sensitive_tag not in serialized
