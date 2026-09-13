from collections.abc import Iterator
from uuid import uuid4

import pytest
from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.access.permissions import DOCUMENTS_READ, ORGANIZATION_READ, PEOPLE_READ
from app.core.documents.models import (
    Document,
    DocumentPermission,
    DocumentPermissionType,
    DocumentStatus,
)
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
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
def search_db() -> Iterator[sessionmaker[Session]]:
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
def client(search_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = search_db()
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


def _permission(session: Session, code: str) -> Permission:
    permission = session.scalar(select(Permission).where(Permission.code == code))
    if permission is not None:
        return permission
    permission = Permission(code=code, name=code, description=code)
    session.add(permission)
    session.flush()
    return permission


def _user_with_permissions(
    session: Session,
    *,
    organization: Organization,
    label: str,
    permissions: tuple[str, ...],
) -> tuple[User, Role]:
    person = Person(
        first_name=label,
        last_name="Admin",
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
        password_hash=hash_password("Search-Test-Password-123!"),
    )
    role = Role(
        code=f"search-{label.lower()}-{uuid4()}",
        name=f"{label} Search Role",
        organization=organization,
    )
    session.add_all([user, role])
    session.flush()
    for code in permissions:
        role.permission_links.append(RolePermission(permission=_permission(session, code)))
    session.add(
        UserRoleAssignment(
            user=user,
            role=role,
            organization=organization,
            scope_mode=OrganizationScopeMode.SELF,
        )
    )
    session.flush()
    return user, role


def _headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _seed(factory: sessionmaker[Session]):
    with factory() as session:
        holding = Organization(
            name="Novin Holding",
            code=f"H-{uuid4()}",
            organization_type=OrganizationType.HOLDING,
        )
        company_a = Organization(
            name="Alpha Market",
            code=f"ALPHA-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        company_b = Organization(
            name="Alpha Hidden Company",
            code=f"HIDDEN-{uuid4()}",
            organization_type=OrganizationType.COMPANY,
            parent=holding,
        )
        session.add_all([holding, company_a, company_b])
        session.flush()

        actor, actor_role = _user_with_permissions(
            session,
            organization=company_a,
            label="Actor",
            permissions=(ORGANIZATION_READ, PEOPLE_READ, DOCUMENTS_READ),
        )
        acl_user, acl_role = _user_with_permissions(
            session,
            organization=company_a,
            label="Acl",
            permissions=(DOCUMENTS_READ,),
        )
        outsider, _ = _user_with_permissions(
            session,
            organization=company_b,
            label="Outsider",
            permissions=(ORGANIZATION_READ, PEOPLE_READ, DOCUMENTS_READ),
        )

        visible_person = Person(
            first_name="Alpha",
            last_name="Visible",
            email="alpha.visible@test.local",
        )
        hidden_person = Person(
            first_name="Alpha",
            last_name="Hidden",
            email="alpha.hidden@test.local",
        )
        session.add_all([visible_person, hidden_person])
        session.flush()
        session.add_all(
            [
                PersonOrganizationRelationship(
                    person=visible_person,
                    organization=company_a,
                    relationship_code="manager",
                ),
                PersonOrganizationRelationship(
                    person=hidden_person,
                    organization=company_b,
                    relationship_code="manager",
                ),
            ]
        )

        visible_doc = Document(
            title="Alpha Public Contract",
            document_type="contract",
            organization_id=company_a.id,
            created_by=actor.id,
            status=DocumentStatus.ACTIVE,
        )
        hidden_company_doc = Document(
            title="Alpha Hidden Company Contract",
            document_type="contract",
            organization_id=company_b.id,
            created_by=outsider.id,
            status=DocumentStatus.ACTIVE,
        )
        acl_hidden_doc = Document(
            title="Alpha Restricted Contract",
            document_type="contract",
            organization_id=company_a.id,
            created_by=actor.id,
            status=DocumentStatus.ACTIVE,
        )
        session.add_all([visible_doc, hidden_company_doc, acl_hidden_doc])
        session.flush()
        session.add(
            DocumentPermission(
                document=acl_hidden_doc,
                role_id=acl_role.id,
                permission_type=DocumentPermissionType.READ.value,
                is_active=True,
            )
        )
        session.commit()
        return {
            "actor": actor.id,
            "acl_user": acl_user.id,
            "outsider": outsider.id,
            "company_a": company_a.id,
            "company_b": company_b.id,
            "visible_person": visible_person.id,
            "hidden_person": hidden_person.id,
            "visible_doc": visible_doc.id,
            "hidden_company_doc": hidden_company_doc.id,
            "acl_hidden_doc": acl_hidden_doc.id,
        }


def test_search_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/search?q=alpha")
    assert response.status_code == 401


def test_search_is_permission_aware_and_does_not_leak_cross_company_rows(
    client: TestClient,
    search_db: sessionmaker[Session],
) -> None:
    seeded = _seed(search_db)
    response = client.get("/api/v1/search?q=alpha&limit_per_type=20", headers=_headers(seeded["actor"]))
    assert response.status_code == 200, response.text
    payload = response.json()
    ids = {item["id"] for item in payload["results"]}

    assert str(seeded["company_a"]) in ids
    assert str(seeded["company_b"]) not in ids
    assert str(seeded["visible_person"]) in ids
    assert str(seeded["hidden_person"]) not in ids
    assert str(seeded["visible_doc"]) in ids
    assert str(seeded["hidden_company_doc"]) not in ids
    assert str(seeded["acl_hidden_doc"]) not in ids
    assert set(payload["counts"]) == {"organization", "person", "document", "customer", "supplier"}
    assert payload["counts"]["customer"] == 0
    assert all(item["action_path"].startswith("/?view=") for item in payload["results"])


def test_document_acl_is_preserved_in_search(
    client: TestClient,
    search_db: sessionmaker[Session],
) -> None:
    seeded = _seed(search_db)
    response = client.get(
        "/api/v1/search?q=restricted&entity_type=document",
        headers=_headers(seeded["acl_user"]),
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["results"]] == [str(seeded["acl_hidden_doc"])]

    hidden = client.get(
        "/api/v1/search?q=restricted&entity_type=document",
        headers=_headers(seeded["actor"]),
    )
    assert hidden.status_code == 200
    assert hidden.json()["results"] == []


def test_entity_type_filter_and_query_validation(
    client: TestClient,
    search_db: sessionmaker[Session],
) -> None:
    seeded = _seed(search_db)
    people_only = client.get(
        "/api/v1/search?q=alpha&entity_type=person",
        headers=_headers(seeded["actor"]),
    )
    assert people_only.status_code == 200
    assert people_only.json()["counts"].keys() == {"person"}
    assert {item["entity_type"] for item in people_only.json()["results"]} == {"person"}

    too_short = client.get("/api/v1/search?q=a", headers=_headers(seeded["actor"]))
    assert too_short.status_code == 422
    whitespace = client.get("/api/v1/search?q=%20%20", headers=_headers(seeded["actor"]))
    assert whitespace.status_code == 422
    too_large_limit = client.get(
        "/api/v1/search?q=alpha&limit_per_type=21",
        headers=_headers(seeded["actor"]),
    )
    assert too_large_limit.status_code == 422
