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
from app.modules.suppliers.models import SupplierExternalReference, SupplierRepresentative
from app.modules.suppliers.permissions import (
    SUPPLIER_ASSIGN,
    SUPPLIER_EXTERNAL_REFERENCE_MANAGE,
    SUPPLIER_EXTERNAL_REFERENCE_READ,
    SUPPLIER_MANAGE,
    SUPPLIER_NOTES_MANAGE,
    SUPPLIER_NOTES_READ,
    SUPPLIER_READ,
    SUPPLIER_REPRESENTATIVE_CONTACT_READ,
    SUPPLIER_REPRESENTATIVE_MANAGE,
    SUPPLIER_REPRESENTATIVE_READ,
    SUPPLIER_TAGS_ASSIGN,
    SUPPLIER_TAGS_CATALOG_MANAGE,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

ALL_SUPPLIER_PERMISSIONS = (
    SUPPLIER_READ,
    SUPPLIER_MANAGE,
    SUPPLIER_REPRESENTATIVE_READ,
    SUPPLIER_REPRESENTATIVE_MANAGE,
    SUPPLIER_REPRESENTATIVE_CONTACT_READ,
    SUPPLIER_NOTES_READ,
    SUPPLIER_NOTES_MANAGE,
    SUPPLIER_ASSIGN,
    SUPPLIER_TAGS_CATALOG_MANAGE,
    SUPPLIER_TAGS_ASSIGN,
    SUPPLIER_EXTERNAL_REFERENCE_READ,
    SUPPLIER_EXTERNAL_REFERENCE_MANAGE,
)


@pytest.fixture
def supplier_db() -> Iterator[sessionmaker[Session]]:
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
def client(supplier_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = supplier_db()
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
        first_name=label, last_name="User", email=f"{label.lower()}-{uuid4()}@test.local"
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
        password_hash=hash_password("Supplier-Test-Password-123!"),
    )
    role = Role(code=f"supplier-role-{uuid4()}", name="Supplier role", organization=organization)
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
            name="Holding", code=f"H-{uuid4()}", organization_type=OrganizationType.HOLDING
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
            permission_codes=ALL_SUPPLIER_PERMISSIONS,
            label="Admin",
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
        )
        manager_a = _seed_user(
            session,
            organization=branch_a,
            permission_codes=ALL_SUPPLIER_PERMISSIONS,
            label="ManagerA",
        )
        manager_b = _seed_user(
            session,
            organization=branch_b,
            permission_codes=ALL_SUPPLIER_PERMISSIONS,
            label="ManagerB",
        )
        reader_a = _seed_user(
            session,
            organization=branch_a,
            permission_codes=(SUPPLIER_READ, SUPPLIER_REPRESENTATIVE_READ),
            label="ReaderA",
        )
        no_supplier = _seed_user(
            session, organization=branch_a, permission_codes=(), label="NoSupplier"
        )
        session.commit()
        return {
            "holding": holding.id,
            "branch_a": branch_a.id,
            "branch_b": branch_b.id,
            "admin": admin.id,
            "manager_a": manager_a.id,
            "manager_b": manager_b.id,
            "reader_a": reader_a.id,
            "no_supplier": no_supplier.id,
        }


def _create_supplier(
    client: TestClient,
    actor_id: UUID,
    organization_id: UUID,
    *,
    name: str = "Supplier Alpha",
) -> dict:
    response = client.post(
        "/api/v1/suppliers",
        headers=headers(actor_id),
        json={"organization_id": str(organization_id), "display_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_supplier_identity_is_independent_and_cross_org_access_is_hidden(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    assert supplier["organization_id"] == str(ids["branch_a"])

    denied = client.get(f"/api/v1/suppliers/{supplier['id']}", headers=headers(ids["manager_b"]))
    assert denied.status_code == 404
    denied_update = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=headers(ids["manager_b"]),
        json={"expected_version": 1, "display_name": "Leak"},
    )
    assert denied_update.status_code == 404

    with supplier_db() as session:
        assert session.scalar(select(Person).where(Person.first_name == "Supplier Alpha")) is None


def test_only_one_active_primary_representative_is_enforced_by_db_index(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    first = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={"display_name": "Rep One", "phone": "+989121111111", "is_primary": True},
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={"display_name": "Rep Two", "phone": "+989122222222", "is_primary": True},
    )
    assert second.status_code == 409

    with supplier_db() as session:
        rows = session.scalars(
            select(SupplierRepresentative).where(
                SupplierRepresentative.supplier_id == UUID(supplier["id"])
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].is_primary is True


def test_representative_contact_is_masked_without_explicit_contact_permission(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    created = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={
            "display_name": "Contact Rep",
            "phone": "+989123456789",
            "email": "rep.secret@example.com",
        },
    )
    assert created.status_code == 201
    assert created.json()["contact_masked"] is False

    masked = client.get(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["reader_a"]),
    )
    assert masked.status_code == 200
    body = masked.json()[0]
    assert body["contact_masked"] is True
    assert body["phone"] == "***6789"
    assert body["email"] == "r***@example.com"
    assert "+989123456789" not in masked.text
    assert "rep.secret@example.com" not in masked.text


def test_representative_pii_and_note_body_do_not_enter_audit(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    phone = "+989199999999"
    email = "pii-secret@example.com"
    note_secret = "CARD 6037999999999999 CVV 123 SUPPLIER-NOTE-SECRET"
    rep = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={"display_name": "Sensitive Rep", "phone": phone, "email": email},
    )
    assert rep.status_code == 201
    note = client.post(
        f"/api/v1/suppliers/{supplier['id']}/notes",
        headers=headers(ids["manager_a"]),
        json={"body": note_secret},
    )
    assert note.status_code == 201

    with supplier_db() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.action.like("supplier.%"))
        ).all()
        serialized = " ".join(
            str((e.before_state, e.after_state, e.event_metadata)) for e in events
        )
        assert phone not in serialized
        assert email not in serialized
        assert note_secret not in serialized
        assert "Sensitive Rep" not in serialized


def test_tag_catalog_permission_is_separate_from_tag_assignment(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    with supplier_db() as session:
        org = session.get(Organization, ids["branch_a"])
        assert org is not None
        catalog_only = _seed_user(
            session,
            organization=org,
            permission_codes=(SUPPLIER_TAGS_CATALOG_MANAGE,),
            label="CatalogOnly",
        )
        assign_only = _seed_user(
            session,
            organization=org,
            permission_codes=(SUPPLIER_READ, SUPPLIER_TAGS_ASSIGN),
            label="AssignOnly",
        )
        session.commit()
        catalog_id, assign_id = catalog_only.id, assign_only.id

    tag = client.post(
        "/api/v1/suppliers/tags/catalog",
        headers=headers(catalog_id),
        json={"organization_id": str(ids["branch_a"]), "name": "Strategic"},
    )
    assert tag.status_code == 201, tag.text

    cannot_attach = client.post(
        f"/api/v1/suppliers/{supplier['id']}/tags/{tag.json()['id']}",
        headers=headers(catalog_id),
    )
    assert cannot_attach.status_code == 404

    cannot_create = client.post(
        "/api/v1/suppliers/tags/catalog",
        headers=headers(assign_id),
        json={"organization_id": str(ids["branch_a"]), "name": "Another"},
    )
    assert cannot_create.status_code == 403

    can_attach = client.post(
        f"/api/v1/suppliers/{supplier['id']}/tags/{tag.json()['id']}",
        headers=headers(assign_id),
    )
    assert can_attach.status_code == 200
    assert [item["name"] for item in can_attach.json()["tags"]] == ["Strategic"]


def test_external_id_nfkc_trim_normalization_preserves_case_and_db_uniqueness(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier_a = _create_supplier(client, ids["manager_a"], ids["branch_a"], name="Supplier A")
    supplier_b = _create_supplier(client, ids["manager_a"], ids["branch_a"], name="Supplier B")

    created = client.post(
        f"/api/v1/suppliers/{supplier_a['id']}/external-references",
        headers=headers(ids["manager_a"]),
        json={"system": "erp", "external_id": "  ＡBC-001  "},
    )
    assert created.status_code == 201, created.text
    assert created.json()["external_id"] == "ABC-001"

    duplicate = client.post(
        f"/api/v1/suppliers/{supplier_b['id']}/external-references",
        headers=headers(ids["manager_a"]),
        json={"system": "erp", "external_id": "ABC-001"},
    )
    assert duplicate.status_code == 409

    case_distinct = client.post(
        f"/api/v1/suppliers/{supplier_b['id']}/external-references",
        headers=headers(ids["manager_a"]),
        json={"system": "erp", "external_id": "abc-001"},
    )
    assert case_distinct.status_code == 201

    with supplier_db() as session:
        refs = session.scalars(
            select(SupplierExternalReference).where(
                SupplierExternalReference.organization_id == ids["branch_a"]
            )
        ).all()
        assert {ref.normalized_external_id for ref in refs} == {"ABC-001", "abc-001"}


def test_external_id_control_characters_are_rejected_and_never_used_in_url(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    rejected = client.post(
        f"/api/v1/suppliers/{supplier['id']}/external-references",
        headers=headers(ids["manager_a"]),
        json={"system": "accounting", "external_id": "ABC\n123"},
    )
    assert rejected.status_code == 422


def test_notes_and_representatives_require_base_supplier_read(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    with supplier_db() as session:
        org = session.get(Organization, ids["branch_a"])
        assert org is not None
        specialized = _seed_user(
            session,
            organization=org,
            permission_codes=(SUPPLIER_NOTES_READ, SUPPLIER_REPRESENTATIVE_READ),
            label="Specialized",
        )
        session.commit()
        specialized_id = specialized.id

    notes = client.get(f"/api/v1/suppliers/{supplier['id']}/notes", headers=headers(specialized_id))
    reps = client.get(
        f"/api/v1/suppliers/{supplier['id']}/representatives", headers=headers(specialized_id)
    )
    assert notes.status_code == 404
    assert reps.status_code == 404


def test_supplier_and_note_optimistic_concurrency_and_archive_restore(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    updated = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "commercial_status": "active"},
    )
    assert updated.status_code == 200
    stale = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "display_name": "stale"},
    )
    assert stale.status_code == 409

    note = client.post(
        f"/api/v1/suppliers/{supplier['id']}/notes",
        headers=headers(ids["manager_a"]),
        json={"body": "one"},
    )
    assert note.status_code == 201
    note_update = client.patch(
        f"/api/v1/suppliers/{supplier['id']}/notes/{note.json()['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "body": "two"},
    )
    assert note_update.status_code == 200
    note_stale = client.patch(
        f"/api/v1/suppliers/{supplier['id']}/notes/{note.json()['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "body": "three"},
    )
    assert note_stale.status_code == 409

    archived = client.post(
        f"/api/v1/suppliers/{supplier['id']}/status",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 2, "is_active": False},
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["commercial_status"] == "archived"
    restored = client.post(
        f"/api/v1/suppliers/{supplier['id']}/status",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 3, "is_active": True},
    )
    assert restored.status_code == 200
    assert restored.json()["commercial_status"] == "inactive"
    assert restored.json()["is_active"] is True


def test_assignment_requires_valid_supplier_context_and_does_not_grant_access(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    invalid = client.post(
        f"/api/v1/suppliers/{supplier['id']}/assign",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "assigned_owner_user_id": str(ids["no_supplier"])},
    )
    assert invalid.status_code == 422
    denied = client.get(f"/api/v1/suppliers/{supplier['id']}", headers=headers(ids["no_supplier"]))
    assert denied.status_code == 404


def test_search_reuses_supplier_acl_before_limit(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    _create_supplier(client, ids["manager_a"], ids["branch_a"], name="Alpha Supplier A")
    _create_supplier(client, ids["manager_b"], ids["branch_b"], name="Alpha Supplier B")

    a_search = client.get(
        "/api/v1/search?q=Alpha&entity_type=supplier&limit_per_type=20",
        headers=headers(ids["reader_a"]),
    )
    assert a_search.status_code == 200, a_search.text
    assert [item["title"] for item in a_search.json()["results"]] == ["Alpha Supplier A"]

    admin_search = client.get(
        "/api/v1/search?q=Alpha&entity_type=supplier&limit_per_type=20",
        headers=headers(ids["admin"]),
    )
    assert admin_search.status_code == 200
    assert {item["title"] for item in admin_search.json()["results"]} == {
        "Alpha Supplier A",
        "Alpha Supplier B",
    }


def test_primary_collision_on_update_and_representative_version_is_enforced(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    primary = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={"display_name": "Primary", "is_primary": True},
    )
    secondary = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={"display_name": "Secondary", "is_primary": False},
    )
    assert primary.status_code == 201 and secondary.status_code == 201

    collision = client.patch(
        f"/api/v1/suppliers/{supplier['id']}/representatives/{secondary.json()['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "is_primary": True},
    )
    assert collision.status_code == 409

    updated = client.patch(
        f"/api/v1/suppliers/{supplier['id']}/representatives/{secondary.json()['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "job_title": "Sales Rep"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    stale = client.patch(
        f"/api/v1/suppliers/{supplier['id']}/representatives/{secondary.json()['id']}",
        headers=headers(ids["manager_a"]),
        json={"expected_version": 1, "is_active": False},
    )
    assert stale.status_code == 409


def test_contact_read_permission_reveals_raw_contact_only_with_base_context(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    raw_phone = "+989121234567"
    raw_email = "raw-contact@example.com"
    created = client.post(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(ids["manager_a"]),
        json={"display_name": "Raw Contact", "phone": raw_phone, "email": raw_email},
    )
    assert created.status_code == 201

    with supplier_db() as session:
        org = session.get(Organization, ids["branch_a"])
        assert org is not None
        contact_reader = _seed_user(
            session,
            organization=org,
            permission_codes=(
                SUPPLIER_READ,
                SUPPLIER_REPRESENTATIVE_READ,
                SUPPLIER_REPRESENTATIVE_CONTACT_READ,
            ),
            label="ContactReader",
        )
        contact_only = _seed_user(
            session,
            organization=org,
            permission_codes=(SUPPLIER_REPRESENTATIVE_CONTACT_READ,),
            label="ContactOnly",
        )
        session.commit()
        contact_reader_id, contact_only_id = contact_reader.id, contact_only.id

    visible = client.get(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(contact_reader_id),
    )
    assert visible.status_code == 200
    assert visible.json()[0]["phone"] == raw_phone
    assert visible.json()[0]["email"] == raw_email
    assert visible.json()[0]["contact_masked"] is False

    denied = client.get(
        f"/api/v1/suppliers/{supplier['id']}/representatives",
        headers=headers(contact_only_id),
    )
    assert denied.status_code == 404


def test_external_reference_read_permission_still_requires_base_supplier_read(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    created = client.post(
        f"/api/v1/suppliers/{supplier['id']}/external-references",
        headers=headers(ids["manager_a"]),
        json={"system": "accounting", "external_id": "ACC-100"},
    )
    assert created.status_code == 201

    with supplier_db() as session:
        org = session.get(Organization, ids["branch_a"])
        assert org is not None
        ref_only = _seed_user(
            session,
            organization=org,
            permission_codes=(SUPPLIER_EXTERNAL_REFERENCE_READ,),
            label="RefOnly",
        )
        session.commit()
        ref_only_id = ref_only.id

    denied = client.get(
        f"/api/v1/suppliers/{supplier['id']}/external-references",
        headers=headers(ref_only_id),
    )
    assert denied.status_code == 404


def test_tag_name_and_external_id_are_excluded_from_audit_payloads(
    client: TestClient,
    supplier_db: sessionmaker[Session],
) -> None:
    ids = _seed_tree(supplier_db)
    supplier = _create_supplier(client, ids["manager_a"], ids["branch_a"])
    tag_secret = "SECRET-TAG-TEXT"
    external_secret = "SECRET-EXTERNAL-ID-777"
    tag = client.post(
        "/api/v1/suppliers/tags/catalog",
        headers=headers(ids["manager_a"]),
        json={"organization_id": str(ids["branch_a"]), "name": tag_secret},
    )
    assert tag.status_code == 201
    external = client.post(
        f"/api/v1/suppliers/{supplier['id']}/external-references",
        headers=headers(ids["manager_a"]),
        json={"system": "erp", "external_id": external_secret},
    )
    assert external.status_code == 201

    with supplier_db() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.action.like("supplier.%"))
        ).all()
        serialized = " ".join(
            str((e.before_state, e.after_state, e.event_metadata)) for e in events
        )
        assert tag_secret not in serialized
        assert external_secret not in serialized
