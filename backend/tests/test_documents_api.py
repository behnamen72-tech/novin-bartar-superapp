from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from app.core.documents.dependencies import get_document_storage
from app.core.documents.models import (
    Document,
    DocumentCategory,
    DocumentLink,
    DocumentPermission,
    DocumentStatus,
    DocumentVersion,
    StorageObject,
)
from app.core.documents.storage.local import LocalStorageProvider
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def documents_db() -> Iterator[sessionmaker[Session]]:
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
def storage(tmp_path: Path) -> LocalStorageProvider:
    return LocalStorageProvider(str(tmp_path / "documents"))


@pytest.fixture
def client(
    documents_db: sessionmaker[Session],
    storage: LocalStorageProvider,
) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = documents_db()
        try:
            yield db
        finally:
            db.close()

    def override_storage() -> LocalStorageProvider:
        return storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_document_storage] = override_storage
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def seed_documents_case(
    factory: sessionmaker[Session],
    *,
    grant_read: bool = True,
    grant_manage: bool = True,
    grant_people_read: bool = True,
    grant_audit_read: bool = False,
) -> tuple[User, Organization, Organization]:
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
        company_b = Organization(
            name="Company B",
            code=f"B-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        person = Person(
            first_name="Document",
            last_name="Admin",
            email=f"docs-{uuid4()}@example.com",
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
            email=person.email or "docs@example.com",
            username=f"docs-{uuid4()}",
            password_hash=hash_password("Documents-password-123!"),
        )
        role = Role(code=f"docs-role-{uuid4()}", name="Documents Role")
        session.add_all([holding, company_a, company_b, person, user, role])
        session.flush()

        if grant_read:
            read_permission = Permission(
                code=f"documents.read.{uuid4()}",
                name="Read documents",
                description="Read documents",
            )
            # The engine checks canonical permission code, so keep exact code.
            read_permission.code = "documents.read"
            session.add(read_permission)
            session.flush()
            session.add(RolePermission(role=role, permission=read_permission))

        if grant_manage:
            manage_permission = Permission(
                code="documents.manage",
                name="Manage documents",
                description="Manage documents",
            )
            session.add(manage_permission)
            session.flush()
            session.add(RolePermission(role=role, permission=manage_permission))

        if grant_people_read:
            people_read_permission = Permission(
                code="people.read",
                name="Read people",
                description="Read people",
            )
            session.add(people_read_permission)
            session.flush()
            session.add(RolePermission(role=role, permission=people_read_permission))

        if grant_audit_read:
            audit_read_permission = Permission(
                code="audit.read",
                name="Read audit",
                description="Read audit",
            )
            session.add(audit_read_permission)
            session.flush()
            session.add(RolePermission(role=role, permission=audit_read_permission))

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




def seed_additional_document_user(
    factory: sessionmaker[Session],
    *,
    organization: Organization,
    permission_codes: tuple[str, ...],
    label: str,
) -> tuple[User, Role]:
    with factory() as session:
        organization_db = session.get(Organization, organization.id)
        assert organization_db is not None

        person = Person(
            first_name=label,
            last_name="User",
            email=f"{label.lower()}-{uuid4()}@example.com",
        )
        session.add(
            PersonOrganizationRelationship(
                person=person,
                organization=organization_db,
                relationship_code="employee",
            )
        )
        user = User(
            person=person,
            email=person.email or f"{label.lower()}@example.com",
            username=f"{label.lower()}-{uuid4()}",
            password_hash=hash_password("Documents-password-123!"),
        )
        role = Role(code=f"{label.lower()}-role-{uuid4()}", name=f"{label} Role")
        session.add_all([person, user, role])
        session.flush()

        for code in permission_codes:
            permission = session.scalar(select(Permission).where(Permission.code == code))
            if permission is None:
                permission = Permission(
                    code=code,
                    name=code,
                    description=f"Test permission {code}",
                )
                session.add(permission)
                session.flush()
            session.add(RolePermission(role=role, permission=permission))

        session.add(
            UserRoleAssignment(
                user=user,
                role=role,
                organization=organization_db,
                scope_mode=OrganizationScopeMode.SELF,
            )
        )
        session.commit()
        return user, role


def role_id_for_user(
    factory: sessionmaker[Session],
    *,
    user_id: UUID,
) -> UUID:
    with factory() as session:
        role_id = session.scalar(
            select(UserRoleAssignment.role_id).where(
                UserRoleAssignment.user_id == user_id
            )
        )
        assert role_id is not None
        return role_id


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def create_document_via_api(
    client: TestClient,
    user: User,
    organization: Organization,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers(user),
        json={
            "title": "Supplier Contract",
            "document_type": "contract",
            "organization_id": str(organization.id),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_document_and_list_are_scope_filtered(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)
    created = create_document_via_api(client, user, company_a)

    with documents_db() as session:
        session.add(
            Document(
                title="Hidden B Document",
                document_type="contract",
                organization_id=company_b.id,
                created_by=user.id,
            )
        )
        session.commit()

    response = client.get("/api/v1/documents", headers=auth_headers(user))
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert created["id"] in ids
    assert len(ids) == 1

    audit_response = client.get("/api/v1/audit", headers=auth_headers(user))
    # User has no audit.read in this fixture; document Audit still exists but is
    # deliberately not exposed without that permission.
    assert audit_response.status_code == 200
    assert audit_response.json() == []


def test_create_document_outside_scope_is_forbidden(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, _, company_b = seed_documents_case(documents_db)
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers(user),
        json={
            "title": "Forbidden",
            "document_type": "contract",
            "organization_id": str(company_b.id),
        },
    )
    assert response.status_code == 403


def test_create_document_without_manage_permission_is_forbidden(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db, grant_manage=False)
    response = client.post(
        "/api/v1/documents",
        headers=auth_headers(user),
        json={
            "title": "No Manage",
            "document_type": "contract",
            "organization_id": str(company_a.id),
        },
    )
    assert response.status_code == 403


def test_upload_versions_preserves_history_and_writes_audit(
    client: TestClient,
    documents_db: sessionmaker[Session],
    storage: LocalStorageProvider,
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)
    document_id = UUID(str(document["id"]))

    first = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth_headers(user),
        files={"file": ("contract.pdf", b"%PDF-1.4 version-one", "application/pdf")},
    )
    second = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth_headers(user),
        files={"file": ("contract.pdf", b"%PDF-1.4 version-two", "application/pdf")},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["version_number"] == 1
    assert second.json()["version_number"] == 2

    detail = client.get(
        f"/api/v1/documents/{document_id}",
        headers=auth_headers(user),
    )
    assert detail.status_code == 200
    assert [v["version_number"] for v in detail.json()["versions"]] == [1, 2]

    with documents_db() as session:
        versions = list(
            session.scalars(
                select(DocumentVersion)
                .where(DocumentVersion.document_id == document_id)
                .order_by(DocumentVersion.version_number)
            ).all()
        )
        assert len(versions) == 2
        assert all(version.created_by == user.id for version in versions)
        storage_objects = list(session.scalars(select(StorageObject)).all())
        assert len(storage_objects) == 2
        assert all(not Path(obj.object_path).is_absolute() for obj in storage_objects)
        events = list(
            session.scalars(
                select(AuditEvent).where(AuditEvent.resource_id == str(document_id))
            ).all()
        )
        actions = [event.action for event in events]
        assert actions.count("document.created") == 1
        assert actions.count("document.version.created") == 2

        for obj in storage_objects:
            assert storage.read(obj.object_path)


def test_download_requires_scope_and_records_every_successful_download(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)
    document_id = UUID(str(document["id"]))
    upload = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth_headers(user),
        files={"file": ("safe.pdf", b"%PDF-1.4 download-me", "application/pdf")},
    )
    assert upload.status_code == 201

    download = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_headers(user),
    )
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 download-me"
    assert "attachment" in download.headers["content-disposition"]
    assert download.headers["x-content-type-options"] == "nosniff"

    with documents_db() as session:
        event_count = session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == "document.downloaded",
                AuditEvent.resource_id == str(document_id),
            )
        )
        assert event_count == 1

        hidden = Document(
            title="Hidden",
            document_type="contract",
            organization_id=company_b.id,
            created_by=user.id,
        )
        session.add(hidden)
        session.commit()
        hidden_id = hidden.id

    forbidden = client.get(
        f"/api/v1/documents/{hidden_id}/download",
        headers=auth_headers(user),
    )
    assert forbidden.status_code == 403


def test_upload_rejects_path_filename_and_forbidden_extension(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    traversal = client.post(
        f"/api/v1/documents/{document['id']}/versions",
        headers=auth_headers(user),
        files={"file": ("../evil.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert traversal.status_code == 400

    executable = client.post(
        f"/api/v1/documents/{document['id']}/versions",
        headers=auth_headers(user),
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert executable.status_code == 400


def test_local_storage_blocks_traversal_and_stores_relative_keys(tmp_path: Path) -> None:
    storage = LocalStorageProvider(str(tmp_path / "root"))
    key = storage.save("org/doc/file.pdf", b"safe")
    assert key == "org/doc/file.pdf"
    assert not Path(key).is_absolute()
    assert storage.read(key) == b"safe"

    with pytest.raises(ValueError):
        storage.save("../escape.pdf", b"bad")
    with pytest.raises(ValueError):
        storage.save(r"..\escape.pdf", b"bad")
    with pytest.raises(ValueError):
        storage.read("/absolute/path.pdf")
    with pytest.raises(ValueError):
        storage.read(r"C:\absolute\path.pdf")

    storage.discard_uncommitted(key)
    with pytest.raises(FileNotFoundError):
        storage.read(key)


def test_failed_version_transaction_discards_uncommitted_file(
    documents_db: sessionmaker[Session],
    storage: LocalStorageProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.documents.service import create_document_version

    user, company_a, _ = seed_documents_case(documents_db)

    with documents_db() as session:
        user_db = session.get(User, user.id)
        assert user_db is not None
        document = Document(
            title="Rollback test",
            document_type="contract",
            organization_id=company_a.id,
            created_by=user.id,
        )
        session.add(document)
        session.commit()
        document_id = document.id

    with documents_db() as session:
        user_db = session.get(User, user.id)
        assert user_db is not None

        def failing_commit() -> None:
            raise RuntimeError("simulated commit failure")

        monkeypatch.setattr(session, "commit", failing_commit)

        with pytest.raises(RuntimeError, match="simulated commit failure"):
            create_document_version(
                session,
                actor=user_db,
                document_id=document_id,
                filename="rollback.pdf",
                declared_content_type="application/pdf",
                content=b"%PDF-1.4 rollback",
                max_size_bytes=1024 * 1024,
                storage=storage,
            )

    stored_files = [path for path in storage.root.rglob("*") if path.is_file()]
    assert stored_files == []


def test_document_person_link_is_scoped_queryable_and_audited(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    linked = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert linked.status_code == 201, linked.text
    assert linked.json()["entity_type"] == "person"
    assert linked.json()["entity_id"] == str(user.person_id)
    assert linked.json()["is_active"] is True

    duplicate = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert duplicate.status_code == 409

    detail = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(user),
    )
    assert detail.status_code == 200
    assert len(detail.json()["links"]) == 1

    filtered = client.get(
        "/api/v1/documents",
        headers=auth_headers(user),
        params={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [document["id"]]

    with documents_db() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "document.linked",
                AuditEvent.resource_id == str(document["id"]),
            )
        )
        assert event is not None


def test_document_person_link_rejects_cross_organization_target(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    with documents_db() as session:
        outsider = Person(
            first_name="Other",
            last_name="Company",
            email=f"other-{uuid4()}@example.com",
        )
        session.add(outsider)
        session.flush()
        session.add(
            PersonOrganizationRelationship(
                person=outsider,
                organization_id=company_b.id,
                relationship_code="employee",
            )
        )
        session.commit()
        outsider_id = outsider.id

    response = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(outsider_id)},
    )
    assert response.status_code == 404


def test_document_person_link_requires_people_read_permission(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(
        documents_db,
        grant_people_read=False,
    )
    document = create_document_via_api(client, user, company_a)

    response = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert response.status_code == 403


def test_document_organization_link_cannot_cross_owner_boundary(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    owner_link = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "organization", "entity_id": str(company_a.id)},
    )
    assert owner_link.status_code == 201

    cross_company = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "organization", "entity_id": str(company_b.id)},
    )
    assert cross_company.status_code == 404


def test_unlink_is_non_destructive_and_relink_reuses_same_row(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    linked = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert linked.status_code == 201
    link_id = linked.json()["id"]

    removed = client.delete(
        f"/api/v1/documents/{document['id']}/links/{link_id}",
        headers=auth_headers(user),
    )
    assert removed.status_code == 204

    current_links = client.get(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
    )
    assert current_links.status_code == 200
    assert current_links.json() == []

    with documents_db() as session:
        durable_link = session.get(DocumentLink, UUID(link_id))
        assert durable_link is not None
        assert durable_link.is_active is False

    relinked = client.post(
        f"/api/v1/documents/{document['id']}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert relinked.status_code == 201
    assert relinked.json()["id"] == link_id
    assert relinked.json()["is_active"] is True

    with documents_db() as session:
        link_count = session.scalar(select(func.count(DocumentLink.id)))
        assert link_count == 1
        actions = list(
            session.scalars(
                select(AuditEvent.action)
                .where(AuditEvent.resource_id == str(document["id"]))
                .order_by(AuditEvent.occurred_at)
            ).all()
        )
        assert actions.count("document.linked") == 2
        assert actions.count("document.unlinked") == 1


def test_archive_freezes_mutations_but_keeps_download_and_restore(
    client: TestClient,
    documents_db: sessionmaker[Session],
    storage: LocalStorageProvider,
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)
    document_id = document["id"]

    upload = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth_headers(user),
        files={"file": ("archive.pdf", b"%PDF-1.4 retained", "application/pdf")},
    )
    assert upload.status_code == 201

    archived = client.post(
        f"/api/v1/documents/{document_id}/archive",
        headers=auth_headers(user),
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    blocked_upload = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth_headers(user),
        files={"file": ("new.pdf", b"%PDF-1.4 blocked", "application/pdf")},
    )
    assert blocked_upload.status_code == 409

    blocked_link = client.post(
        f"/api/v1/documents/{document_id}/links",
        headers=auth_headers(user),
        json={"entity_type": "person", "entity_id": str(user.person_id)},
    )
    assert blocked_link.status_code == 409

    download = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=auth_headers(user),
    )
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 retained"

    # Archive does not remove committed physical content.
    with documents_db() as session:
        obj = session.scalar(select(StorageObject))
        assert obj is not None
        assert storage.read(obj.object_path) == b"%PDF-1.4 retained"

    restored = client.post(
        f"/api/v1/documents/{document_id}/restore",
        headers=auth_headers(user),
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"

    upload_after_restore = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth_headers(user),
        files={"file": ("new.pdf", b"%PDF-1.4 allowed", "application/pdf")},
    )
    assert upload_after_restore.status_code == 201
    assert upload_after_restore.json()["version_number"] == 2

    with documents_db() as session:
        persisted = session.get(Document, UUID(document_id))
        assert persisted is not None
        assert persisted.status == DocumentStatus.ACTIVE
        actions = list(
            session.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.resource_id == document_id
                )
            ).all()
        )
        assert actions.count("document.archived") == 1
        assert actions.count("document.restored") == 1
        assert actions.count("document.downloaded") == 1


def test_archive_and_restore_are_idempotent_without_duplicate_audit(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    first_archive = client.post(
        f"/api/v1/documents/{document['id']}/archive",
        headers=auth_headers(user),
    )
    second_archive = client.post(
        f"/api/v1/documents/{document['id']}/archive",
        headers=auth_headers(user),
    )
    first_restore = client.post(
        f"/api/v1/documents/{document['id']}/restore",
        headers=auth_headers(user),
    )
    second_restore = client.post(
        f"/api/v1/documents/{document['id']}/restore",
        headers=auth_headers(user),
    )
    assert first_archive.status_code == 200
    assert second_archive.status_code == 200
    assert first_restore.status_code == 200
    assert second_restore.status_code == 200

    with documents_db() as session:
        archived_count = session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == "document.archived",
                AuditEvent.resource_id == str(document["id"]),
            )
        )
        restored_count = session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.action == "document.restored",
                AuditEvent.resource_id == str(document["id"]),
            )
        )
        assert archived_count == 1
        assert restored_count == 1


def test_document_link_filter_requires_type_and_id_together(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, _, _ = seed_documents_case(documents_db)

    only_type = client.get(
        "/api/v1/documents",
        headers=auth_headers(user),
        params={"entity_type": "person"},
    )
    assert only_type.status_code == 400

    only_id = client.get(
        "/api/v1/documents",
        headers=auth_headers(user),
        params={"entity_id": str(user.person_id)},
    )
    assert only_id.status_code == 400


def test_document_acl_defaults_to_inherited_then_hides_restricted_document(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    viewer, _ = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read",),
        label="Viewer",
    )
    document = create_document_via_api(client, owner, company_a)

    inherited = client.get("/api/v1/documents", headers=auth_headers(viewer))
    assert inherited.status_code == 200
    assert document["id"] in {item["id"] for item in inherited.json()}

    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)
    restricted = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    )
    assert restricted.status_code == 201, restricted.text

    hidden_list = client.get("/api/v1/documents", headers=auth_headers(viewer))
    assert hidden_list.status_code == 200
    assert document["id"] not in {item["id"] for item in hidden_list.json()}

    hidden_detail = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(viewer),
    )
    assert hidden_detail.status_code == 404


def test_first_document_acl_must_preserve_current_manager_control(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    _, other_manager_role = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read", "documents.manage"),
        label="OtherManager",
    )
    document = create_document_via_api(client, owner, company_a)

    first_read = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(other_manager_role.id), "permission_type": "read"},
    )
    assert first_read.status_code == 409

    first_other_manager = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(other_manager_role.id), "permission_type": "manage"},
    )
    assert first_other_manager.status_code == 409

    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)
    first_owner_manager = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    )
    assert first_owner_manager.status_code == 201


def test_document_read_acl_allows_reader_but_not_management(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    viewer, viewer_role = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read",),
        label="RestrictedReader",
    )
    document = create_document_via_api(client, owner, company_a)
    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)

    assert client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    ).status_code == 201
    read_grant = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(viewer_role.id), "permission_type": "read"},
    )
    assert read_grant.status_code == 201, read_grant.text

    visible = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(viewer),
    )
    assert visible.status_code == 200

    cannot_archive = client.post(
        f"/api/v1/documents/{document['id']}/archive",
        headers=auth_headers(viewer),
    )
    assert cannot_archive.status_code == 403


def test_document_manage_acl_controls_mutations_for_same_org_manager(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    manager, manager_role = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read", "documents.manage"),
        label="ScopedManager",
    )
    document = create_document_via_api(client, owner, company_a)
    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)

    assert client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    ).status_code == 201

    blocked = client.post(
        f"/api/v1/documents/{document['id']}/archive",
        headers=auth_headers(manager),
    )
    assert blocked.status_code == 404

    grant = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(manager_role.id), "permission_type": "manage"},
    )
    assert grant.status_code == 201

    allowed = client.post(
        f"/api/v1/documents/{document['id']}/archive",
        headers=auth_headers(manager),
    )
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "archived"


def test_document_acl_revoke_prevents_managerless_restricted_state_and_can_return_to_inherited(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    viewer, viewer_role = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read",),
        label="AclViewer",
    )
    document = create_document_via_api(client, owner, company_a)
    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)

    manage_grant = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    )
    read_grant = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(viewer_role.id), "permission_type": "read"},
    )
    assert manage_grant.status_code == 201
    assert read_grant.status_code == 201

    blocked = client.delete(
        f"/api/v1/documents/{document['id']}/permissions/{manage_grant.json()['id']}",
        headers=auth_headers(owner),
    )
    assert blocked.status_code == 409

    remove_read = client.delete(
        f"/api/v1/documents/{document['id']}/permissions/{read_grant.json()['id']}",
        headers=auth_headers(owner),
    )
    assert remove_read.status_code == 204
    remove_last = client.delete(
        f"/api/v1/documents/{document['id']}/permissions/{manage_grant.json()['id']}",
        headers=auth_headers(owner),
    )
    assert remove_last.status_code == 204

    inherited_again = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(viewer),
    )
    assert inherited_again.status_code == 200

    with documents_db() as session:
        active_acl_count = session.scalar(
            select(func.count(DocumentPermission.id)).where(
                DocumentPermission.document_id == UUID(document["id"]),
                DocumentPermission.is_active.is_(True),
            )
        )
        assert active_acl_count == 0
        actions = list(
            session.scalars(
                select(AuditEvent.action).where(
                    AuditEvent.resource_id == document["id"],
                    AuditEvent.action.in_(
                        (
                            "document.permission.granted",
                            "document.permission.revoked",
                        )
                    ),
                )
            ).all()
        )
        assert actions.count("document.permission.granted") == 2
        assert actions.count("document.permission.revoked") == 2


def test_document_acl_rejects_role_without_required_base_permission(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    _, reader_role = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read",),
        label="ReaderOnly",
    )
    document = create_document_via_api(client, owner, company_a)
    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)
    assert client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    ).status_code == 201

    invalid_manage = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(reader_role.id), "permission_type": "manage"},
    )
    assert invalid_manage.status_code == 404


def test_access_manage_can_recover_acl_without_gaining_document_content_access(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    recovery_manager, recovery_role = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read", "documents.manage"),
        label="RecoveryManager",
    )
    access_admin, _ = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("access.manage",),
        label="AccessAdmin",
    )
    document = create_document_via_api(client, owner, company_a)
    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)
    first = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    )
    assert first.status_code == 201

    # access.manage is deliberately an ACL-administration recovery path only.
    no_content_access = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(access_admin),
    )
    assert no_content_access.status_code == 403

    permissions = client.get(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(access_admin),
    )
    assert permissions.status_code == 200

    recovery_grant = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(access_admin),
        json={"role_id": str(recovery_role.id), "permission_type": "manage"},
    )
    assert recovery_grant.status_code == 201, recovery_grant.text

    recovered = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(recovery_manager),
    )
    assert recovered.status_code == 200


def test_document_acl_role_from_other_organization_does_not_match(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, company_b = seed_documents_case(documents_db)
    _, other_org_role = seed_additional_document_user(
        documents_db,
        organization=company_b,
        permission_codes=("documents.read",),
        label="OtherOrgReader",
    )
    document = create_document_via_api(client, owner, company_a)
    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)
    assert client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    ).status_code == 201

    cross_scope_grant = client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(other_org_role.id), "permission_type": "read"},
    )
    assert cross_scope_grant.status_code == 404


def test_manage_only_user_can_upload_without_post_commit_read_failure(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    manager, company_a, _ = seed_documents_case(
        documents_db,
        grant_read=False,
        grant_manage=True,
    )
    document = create_document_via_api(client, manager, company_a)

    upload = client.post(
        f"/api/v1/documents/{document['id']}/versions",
        headers=auth_headers(manager),
        files={"file": ("manage-only.pdf", b"%PDF-1.4 manage-only", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["version_number"] == 1

    # The separate read permission is still enforced for content access.
    detail = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(manager),
    )
    assert detail.status_code == 403


def test_b55_category_hierarchy_scope_and_duplicate_code(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)

    root = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "contracts",
            "name": "Contracts",
        },
    )
    assert root.status_code == 201, root.text

    child = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "purchase-contracts",
            "name": "Purchase Contracts",
            "parent_id": root.json()["id"],
        },
    )
    assert child.status_code == 201, child.text
    assert child.json()["parent_id"] == root.json()["id"]

    duplicate = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "contracts",
            "name": "Duplicate",
        },
    )
    assert duplicate.status_code == 409

    outside_scope = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_b.id),
            "code": "hidden",
            "name": "Hidden",
        },
    )
    assert outside_scope.status_code == 403

    listed = client.get(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        params={"organization_id": str(company_a.id)},
    )
    assert listed.status_code == 200
    assert {item["code"] for item in listed.json()} == {"contracts", "purchase-contracts"}


def test_b55_category_cycle_and_soft_deactivation_rules(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    root = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={"organization_id": str(company_a.id), "code": "root", "name": "Root"},
    ).json()
    child = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "child",
            "name": "Child",
            "parent_id": root["id"],
        },
    ).json()

    cycle = client.patch(
        f"/api/v1/document-categories/{root['id']}",
        headers=auth_headers(user),
        json={"parent_id": child["id"]},
    )
    assert cycle.status_code == 409

    parent_first = client.delete(
        f"/api/v1/document-categories/{root['id']}",
        headers=auth_headers(user),
    )
    assert parent_first.status_code == 409

    assert client.delete(
        f"/api/v1/document-categories/{child['id']}",
        headers=auth_headers(user),
    ).status_code == 204
    assert client.delete(
        f"/api/v1/document-categories/{root['id']}",
        headers=auth_headers(user),
    ).status_code == 204

    assert client.post(
        f"/api/v1/document-categories/{root['id']}/restore",
        headers=auth_headers(user),
    ).status_code == 200
    assert client.post(
        f"/api/v1/document-categories/{child['id']}/restore",
        headers=auth_headers(user),
    ).status_code == 200

    with documents_db() as session:
        persisted = session.get(DocumentCategory, UUID(child["id"]))
        assert persisted is not None and persisted.is_active is True


def test_b55_metadata_category_expiration_search_and_audit(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)
    category = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "licenses",
            "name": "Licenses",
        },
    ).json()
    expires_at = (datetime.now(UTC) + timedelta(days=20)).isoformat()

    updated = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={
            "title": "Branch License Renewal",
            "description": "Renewal package for the central branch",
            "document_type": "license",
            "priority": "high",
            "category_id": category["id"],
            "expires_at": expires_at,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["title"] == "Branch License Renewal"
    assert body["document_type"] == "license"
    assert body["priority"] == "high"
    assert body["category_id"] == category["id"]
    assert body["expires_at"] is not None

    search = client.get(
        "/api/v1/documents",
        headers=auth_headers(user),
        params={
            "q": "renewal",
            "category_id": category["id"],
            "priority": "high",
        },
    )
    assert search.status_code == 200
    assert [item["id"] for item in search.json()] == [document["id"]]

    with documents_db() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "document.metadata.updated",
                AuditEvent.resource_id == str(document["id"]),
            )
        )
        assert event is not None
        assert "category_id" in (event.event_metadata or {}).get("changed_fields", [])
        assert "expires_at" in (event.event_metadata or {}).get("changed_fields", [])


def test_b55_metadata_rejects_cross_org_category_and_archived_mutation(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    with documents_db() as session:
        foreign_category = DocumentCategory(
            organization_id=company_b.id,
            code="foreign",
            name="Foreign",
            is_active=True,
        )
        session.add(foreign_category)
        session.commit()
        foreign_category_id = foreign_category.id

    cross_org = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={"category_id": str(foreign_category_id)},
    )
    assert cross_org.status_code == 404

    assert client.post(
        f"/api/v1/documents/{document['id']}/archive",
        headers=auth_headers(user),
    ).status_code == 200
    frozen = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={"description": "must not change"},
    )
    assert frozen.status_code == 409


def test_b55_retention_policy_snapshot_does_not_retroactively_change(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)
    policy = client.post(
        "/api/v1/document-retention-policies",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "contracts-365",
            "name": "Contracts 365",
            "retention_days": 365,
            "basis": "created_at",
        },
    )
    assert policy.status_code == 201, policy.text

    assigned = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={"retention_policy_id": policy.json()["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    original_deadline = assigned.json()["retention_review_at"]
    assert original_deadline is not None

    changed_policy = client.patch(
        f"/api/v1/document-retention-policies/{policy.json()['id']}",
        headers=auth_headers(user),
        json={"retention_days": 730},
    )
    assert changed_policy.status_code == 200

    detail = client.get(
        f"/api/v1/documents/{document['id']}",
        headers=auth_headers(user),
    )
    assert detail.status_code == 200
    assert detail.json()["retention_review_at"] == original_deadline


def test_b55_expires_based_retention_requires_expiry_and_recalculates_on_change(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)
    policy = client.post(
        "/api/v1/document-retention-policies",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "after-expiry",
            "name": "After expiry",
            "retention_days": 30,
            "basis": "expires_at",
        },
    ).json()

    missing_expiry = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={"retention_policy_id": policy["id"]},
    )
    assert missing_expiry.status_code == 400

    first_expiry = datetime.now(UTC) + timedelta(days=10)
    assigned = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={
            "expires_at": first_expiry.isoformat(),
            "retention_policy_id": policy["id"],
        },
    )
    assert assigned.status_code == 200, assigned.text
    first_deadline = datetime.fromisoformat(assigned.json()["retention_review_at"])
    assert first_deadline.date() == (first_expiry + timedelta(days=30)).date()

    second_expiry = first_expiry + timedelta(days=5)
    changed = client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(user),
        json={"expires_at": second_expiry.isoformat()},
    )
    assert changed.status_code == 200
    second_deadline = datetime.fromisoformat(changed.json()["retention_review_at"])
    assert second_deadline.date() == (second_expiry + timedelta(days=30)).date()


def test_b55_inactive_retention_policy_cannot_be_newly_assigned(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    first = create_document_via_api(client, user, company_a)
    second = create_document_via_api(client, user, company_a)
    policy = client.post(
        "/api/v1/document-retention-policies",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "inactive-policy",
            "name": "Inactive policy",
            "retention_days": 90,
            "basis": "created_at",
        },
    ).json()

    assert client.patch(
        f"/api/v1/documents/{first['id']}/metadata",
        headers=auth_headers(user),
        json={"retention_policy_id": policy["id"]},
    ).status_code == 200
    assert client.delete(
        f"/api/v1/document-retention-policies/{policy['id']}",
        headers=auth_headers(user),
    ).status_code == 204

    rejected = client.patch(
        f"/api/v1/documents/{second['id']}/metadata",
        headers=auth_headers(user),
        json={"retention_policy_id": policy["id"]},
    )
    assert rejected.status_code == 404

    # Existing assignment remains a historical/snapshot association.
    detail = client.get(
        f"/api/v1/documents/{first['id']}",
        headers=auth_headers(user),
    )
    assert detail.status_code == 200
    assert detail.json()["retention_policy_id"] == policy["id"]


def test_b55_expiring_list_respects_document_acl(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db)
    viewer, _ = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read",),
        label="ExpiryViewer",
    )
    document = create_document_via_api(client, owner, company_a)
    assert client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(owner),
        json={"expires_at": (datetime.now(UTC) + timedelta(days=5)).isoformat()},
    ).status_code == 200

    visible_before_acl = client.get(
        "/api/v1/documents/expiring",
        headers=auth_headers(viewer),
        params={"within_days": 30},
    )
    assert visible_before_acl.status_code == 200
    assert document["id"] in {item["document"]["id"] for item in visible_before_acl.json()}

    owner_role_id = role_id_for_user(documents_db, user_id=owner.id)
    assert client.post(
        f"/api/v1/documents/{document['id']}/permissions",
        headers=auth_headers(owner),
        json={"role_id": str(owner_role_id), "permission_type": "manage"},
    ).status_code == 201

    hidden_after_acl = client.get(
        "/api/v1/documents/expiring",
        headers=auth_headers(viewer),
        params={"within_days": 30},
    )
    assert hidden_after_acl.status_code == 200
    assert document["id"] not in {item["document"]["id"] for item in hidden_after_acl.json()}


def test_b55_retention_due_list_is_scope_filtered(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, company_b = seed_documents_case(documents_db)
    document = create_document_via_api(client, user, company_a)

    with documents_db() as session:
        owned = session.get(Document, UUID(document["id"]))
        assert owned is not None
        owned.retention_review_at = datetime.now(UTC) - timedelta(days=3)
        hidden = Document(
            title="Other company due",
            document_type="contract",
            organization_id=company_b.id,
            created_by=user.id,
            retention_review_at=datetime.now(UTC) - timedelta(days=10),
        )
        session.add(hidden)
        session.commit()

    due = client.get("/api/v1/documents/retention-due", headers=auth_headers(user))
    assert due.status_code == 200
    assert [item["document"]["id"] for item in due.json()] == [document["id"]]
    assert due.json()[0]["days_overdue"] >= 3


def test_b55_document_timeline_reuses_audit_read_permission(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    owner, company_a, _ = seed_documents_case(documents_db, grant_audit_read=True)
    viewer, _ = seed_additional_document_user(
        documents_db,
        organization=company_a,
        permission_codes=("documents.read",),
        label="NoAuditViewer",
    )
    document = create_document_via_api(client, owner, company_a)
    assert client.patch(
        f"/api/v1/documents/{document['id']}/metadata",
        headers=auth_headers(owner),
        json={"description": "Timeline change"},
    ).status_code == 200

    timeline = client.get(
        f"/api/v1/documents/{document['id']}/timeline",
        headers=auth_headers(owner),
    )
    assert timeline.status_code == 200, timeline.text
    actions = [item["action"] for item in timeline.json()]
    assert "document.created" in actions
    assert "document.metadata.updated" in actions

    denied = client.get(
        f"/api/v1/documents/{document['id']}/timeline",
        headers=auth_headers(viewer),
    )
    assert denied.status_code == 403


def test_b55_retention_policy_and_category_audit_are_persisted(
    client: TestClient,
    documents_db: sessionmaker[Session],
) -> None:
    user, company_a, _ = seed_documents_case(documents_db)
    category = client.post(
        "/api/v1/document-categories",
        headers=auth_headers(user),
        json={"organization_id": str(company_a.id), "code": "audit-cat", "name": "Audit Cat"},
    )
    policy = client.post(
        "/api/v1/document-retention-policies",
        headers=auth_headers(user),
        json={
            "organization_id": str(company_a.id),
            "code": "audit-policy",
            "name": "Audit Policy",
            "retention_days": 10,
            "basis": "created_at",
        },
    )
    assert category.status_code == 201
    assert policy.status_code == 201

    with documents_db() as session:
        category_event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "document.category.created",
                AuditEvent.resource_id == category.json()["id"],
            )
        )
        policy_event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "document.retention_policy.created",
                AuditEvent.resource_id == policy.json()["id"],
            )
        )
        assert category_event is not None
        assert policy_event is not None
