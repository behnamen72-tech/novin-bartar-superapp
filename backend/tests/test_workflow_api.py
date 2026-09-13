from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.access.models import OrganizationScopeMode, Permission, Role, RolePermission, UserRoleAssignment
from app.core.access.permissions import WORKFLOW_EXECUTE, WORKFLOW_MANAGE, WORKFLOW_READ
from app.core.audit.models import AuditEvent
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.notifications.models import Notification
from app.core.people.models import Person, PersonOrganizationRelationship
from app.core.workflow.events import WorkflowHistoryIntegrityError
from app.core.workflow.models import WorkflowInstance, WorkflowInstanceStatus, WorkflowTransitionRecord
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
def workflow_db() -> Iterator[sessionmaker[Session]]:
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
def client(workflow_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = workflow_db()
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


def headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _permission(session: Session, code: str) -> Permission:
    item = session.scalar(select(Permission).where(Permission.code == code))
    if item is not None:
        return item
    item = Permission(code=code, name=code, description=code)
    session.add(item)
    session.flush()
    return item


def _seed_user(
    session: Session,
    *,
    organization: Organization,
    permission_codes: tuple[str, ...],
    scope_mode: OrganizationScopeMode = OrganizationScopeMode.SELF,
    label: str = "Actor",
) -> User:
    person = Person(first_name=label, last_name="User", email=f"{label.lower()}-{uuid4()}@test.local")
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
        password_hash=hash_password("Workflow-Test-Password-123!"),
    )
    role = Role(code=f"workflow-role-{uuid4()}", name="Workflow role", organization=organization)
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


def _seed_tree(factory: sessionmaker[Session]):
    with factory() as session:
        holding = Organization(name="Holding", code=f"H-{uuid4()}", organization_type=OrganizationType.HOLDING)
        company_a = Organization(name="Company A", code=f"A-{uuid4()}", organization_type=OrganizationType.COMPANY, parent=holding)
        branch_a = Organization(name="Branch A", code=f"BA-{uuid4()}", organization_type=OrganizationType.BRANCH, parent=company_a)
        company_b = Organization(name="Company B", code=f"B-{uuid4()}", organization_type=OrganizationType.COMPANY, parent=holding)
        session.add_all([holding, company_a, branch_a, company_b])
        session.flush()
        admin = _seed_user(
            session,
            organization=holding,
            permission_codes=(WORKFLOW_READ, WORKFLOW_MANAGE, WORKFLOW_EXECUTE),
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
            label="Admin",
        )
        outsider = _seed_user(
            session,
            organization=company_b,
            permission_codes=(WORKFLOW_READ, WORKFLOW_EXECUTE),
            label="Outsider",
        )
        session.commit()
        return admin.id, outsider.id, holding.id, company_a.id, branch_a.id, company_b.id


def _create_definition(client: TestClient, actor_id, organization_id, *, scope_mode: str = "self_and_descendants") -> dict:
    response = client.post(
        "/api/v1/workflow/definitions",
        headers=headers(actor_id),
        json={
            "organization_id": str(organization_id),
            "code": "approval",
            "name": "Approval",
            "scope_mode": scope_mode,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_state(client: TestClient, actor_id, definition_id, *, code: str, initial: bool = False, terminal: bool = False) -> dict:
    response = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/states",
        headers=headers(actor_id),
        json={"code": code, "name": code.title(), "is_initial": initial, "is_terminal": terminal},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _publish_two_state_workflow(client: TestClient, actor_id, organization_id, *, scope_mode: str = "self_and_descendants") -> dict:
    definition = _create_definition(client, actor_id, organization_id, scope_mode=scope_mode)
    definition = _add_state(client, actor_id, definition["id"], code="draft", initial=True)
    definition = _add_state(client, actor_id, definition["id"], code="approved", terminal=True)
    states = {item["code"]: item for item in definition["states"]}
    response = client.post(
        f"/api/v1/workflow/definitions/{definition['id']}/transitions",
        headers=headers(actor_id),
        json={
            "code": "approve",
            "name": "Approve",
            "from_state_id": states["draft"]["id"],
            "to_state_id": states["approved"]["id"],
        },
    )
    assert response.status_code == 200, response.text
    definition = response.json()
    response = client.post(
        f"/api/v1/workflow/definitions/{definition['id']}/publish",
        headers=headers(actor_id),
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_workflow_definition_create_is_permissioned_and_audited(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    definition = _create_definition(client, admin_id, holding_id)
    assert definition["version"] == 1
    assert definition["status"] == "draft"

    with workflow_db() as session:
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "workflow.definition.created",
                AuditEvent.resource_id == definition["id"],
            )
        )
        assert audit is not None
        assert audit.organization_id == holding_id


def test_publish_rejects_invalid_definition(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    definition = _create_definition(client, admin_id, holding_id)
    response = client.post(
        f"/api/v1/workflow/definitions/{definition['id']}/publish",
        headers=headers(admin_id),
    )
    assert response.status_code == 400
    assert "initial state" in response.json()["detail"].lower()


def test_published_workflow_runs_to_completion_with_immutable_history(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, branch_id, _ = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, holding_id)
    transition_id = definition["transitions"][0]["id"]

    start = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={
            "definition_id": definition["id"],
            "organization_id": str(branch_id),
            "resource_type": "document",
            "resource_id": str(uuid4()),
        },
    )
    assert start.status_code == 201, start.text
    instance = start.json()
    assert instance["status"] == "active"

    advanced = client.post(
        f"/api/v1/workflow/instances/{instance['id']}/transition",
        headers=headers(admin_id),
        json={"transition_id": transition_id, "comment": "Approved after review"},
    )
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["status"] == "completed"
    assert len(advanced.json()["history"]) == 1

    with workflow_db() as session:
        record = session.scalar(select(WorkflowTransitionRecord))
        assert record is not None
        record.comment = "tampered"
        with pytest.raises(WorkflowHistoryIntegrityError):
            session.flush()


def test_self_scoped_definition_cannot_run_in_descendant(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, branch_id, _ = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, holding_id, scope_mode="self")
    response = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={
            "definition_id": definition["id"],
            "organization_id": str(branch_id),
            "resource_type": "document",
            "resource_id": str(uuid4()),
        },
    )
    assert response.status_code == 404


def test_cross_company_user_cannot_discover_or_start_definition(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, outsider_id, holding_id, company_a_id, _, company_b_id = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, company_a_id)

    get_response = client.get(
        f"/api/v1/workflow/definitions/{definition['id']}?organization_id={company_b_id}",
        headers=headers(outsider_id),
    )
    assert get_response.status_code == 404

    start_response = client.post(
        "/api/v1/workflow/instances",
        headers=headers(outsider_id),
        json={
            "definition_id": definition["id"],
            "organization_id": str(company_b_id),
            "resource_type": "document",
            "resource_id": str(uuid4()),
        },
    )
    assert start_response.status_code == 404


def test_published_definition_is_immutable_and_new_version_is_draft_copy(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, holding_id)

    update = client.patch(
        f"/api/v1/workflow/definitions/{definition['id']}",
        headers=headers(admin_id),
        json={"name": "Changed"},
    )
    assert update.status_code == 409

    clone = client.post(
        f"/api/v1/workflow/definitions/{definition['id']}/new-version",
        headers=headers(admin_id),
    )
    assert clone.status_code == 201, clone.text
    payload = clone.json()
    assert payload["version"] == 2
    assert payload["status"] == "draft"
    assert {s["code"] for s in payload["states"]} == {"draft", "approved"}
    assert {t["code"] for t in payload["transitions"]} == {"approve"}


def test_publishing_new_version_retires_previous_version(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    first = _publish_two_state_workflow(client, admin_id, holding_id)
    clone = client.post(
        f"/api/v1/workflow/definitions/{first['id']}/new-version",
        headers=headers(admin_id),
    ).json()
    published = client.post(
        f"/api/v1/workflow/definitions/{clone['id']}/publish",
        headers=headers(admin_id),
    )
    assert published.status_code == 200, published.text

    old = client.get(
        f"/api/v1/workflow/definitions?organization_id={holding_id}&include_drafts=true",
        headers=headers(admin_id),
    )
    assert old.status_code == 200
    by_version = {item["version"]: item["status"] for item in old.json() if item["code"] == "approval"}
    assert by_version[1] == "retired"
    assert by_version[2] == "published"


def test_wrong_transition_is_rejected_without_history(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, holding_id)
    start = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={
            "definition_id": definition["id"],
            "organization_id": str(holding_id),
            "resource_type": "contract",
            "resource_id": str(uuid4()),
        },
    ).json()
    response = client.post(
        f"/api/v1/workflow/instances/{start['id']}/transition",
        headers=headers(admin_id),
        json={"transition_id": str(uuid4())},
    )
    assert response.status_code == 400
    with workflow_db() as session:
        assert session.scalar(select(WorkflowTransitionRecord.id).limit(1)) is None


def test_active_instance_can_cancel_but_completed_cannot(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, holding_id)
    transition_id = definition["transitions"][0]["id"]

    active = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={"definition_id": definition["id"], "organization_id": str(holding_id), "resource_type": "task", "resource_id": "one"},
    ).json()
    cancelled = client.post(f"/api/v1/workflow/instances/{active['id']}/cancel", headers=headers(admin_id))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    second = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={"definition_id": definition["id"], "organization_id": str(holding_id), "resource_type": "task", "resource_id": "two"},
    ).json()
    client.post(
        f"/api/v1/workflow/instances/{second['id']}/transition",
        headers=headers(admin_id),
        json={"transition_id": transition_id},
    )
    response = client.post(f"/api/v1/workflow/instances/{second['id']}/cancel", headers=headers(admin_id))
    assert response.status_code == 409


def test_workflow_write_endpoints_require_authentication(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    _, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    response = client.post(
        "/api/v1/workflow/definitions",
        json={"organization_id": str(holding_id), "code": "x", "name": "X"},
    )
    assert response.status_code == 401


def test_publish_rejects_unreachable_or_dead_end_states(client: TestClient, workflow_db: sessionmaker[Session]) -> None:
    admin_id, _, holding_id, _, _, _ = _seed_tree(workflow_db)
    definition = _create_definition(client, admin_id, holding_id)
    definition = _add_state(client, admin_id, definition["id"], code="start", initial=True)
    definition = _add_state(client, admin_id, definition["id"], code="done", terminal=True)
    definition = _add_state(client, admin_id, definition["id"], code="orphan")
    states = {item["code"]: item for item in definition["states"]}
    response = client.post(
        f"/api/v1/workflow/definitions/{definition['id']}/transitions",
        headers=headers(admin_id),
        json={
            "code": "finish",
            "name": "Finish",
            "from_state_id": states["start"]["id"],
            "to_state_id": states["done"]["id"],
        },
    )
    assert response.status_code == 200
    publish = client.post(
        f"/api/v1/workflow/definitions/{definition['id']}/publish",
        headers=headers(admin_id),
    )
    assert publish.status_code == 400
    assert "non-terminal state" in publish.json()["detail"].lower()


def test_workflow_organizations_expose_only_effective_capabilities(
    client: TestClient, workflow_db: sessionmaker[Session]
) -> None:
    admin_id, outsider_id, holding_id, company_a_id, branch_a_id, company_b_id = _seed_tree(workflow_db)

    admin_response = client.get(
        "/api/v1/workflow/organizations",
        headers=headers(admin_id),
    )
    assert admin_response.status_code == 200, admin_response.text
    admin_items = {item["id"]: item for item in admin_response.json()}
    assert set(admin_items) == {
        str(holding_id),
        str(company_a_id),
        str(branch_a_id),
        str(company_b_id),
    }
    assert all(
        item["can_read"] and item["can_manage"] and item["can_execute"]
        for item in admin_items.values()
    )

    outsider_response = client.get(
        "/api/v1/workflow/organizations",
        headers=headers(outsider_id),
    )
    assert outsider_response.status_code == 200, outsider_response.text
    outsider_items = outsider_response.json()
    assert len(outsider_items) == 1
    assert outsider_items[0]["id"] == str(company_b_id)
    assert outsider_items[0]["can_read"] is True
    assert outsider_items[0]["can_manage"] is False
    assert outsider_items[0]["can_execute"] is True


def test_workflow_organizations_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/workflow/organizations")
    assert response.status_code == 401


def test_workflow_changes_by_another_actor_notify_instance_starter(
    client: TestClient,
    workflow_db: sessionmaker[Session],
) -> None:
    admin_id, _, holding_id, _, branch_id, _ = _seed_tree(workflow_db)
    definition = _publish_two_state_workflow(client, admin_id, holding_id)
    transition_id = definition["transitions"][0]["id"]

    with workflow_db() as session:
        holding = session.get(Organization, holding_id)
        assert holding is not None
        collaborator = _seed_user(
            session,
            organization=holding,
            permission_codes=(WORKFLOW_EXECUTE,),
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
            label="Collaborator",
        )
        collaborator_id = collaborator.id
        session.commit()

    first = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={
            "definition_id": definition["id"],
            "organization_id": str(branch_id),
            "resource_type": "task",
            "resource_id": "notify-transition",
        },
    )
    assert first.status_code == 201, first.text
    transitioned = client.post(
        f"/api/v1/workflow/instances/{first.json()['id']}/transition",
        headers=headers(collaborator_id),
        json={"transition_id": transition_id},
    )
    assert transitioned.status_code == 200, transitioned.text

    second = client.post(
        "/api/v1/workflow/instances",
        headers=headers(admin_id),
        json={
            "definition_id": definition["id"],
            "organization_id": str(branch_id),
            "resource_type": "task",
            "resource_id": "notify-cancel",
        },
    )
    assert second.status_code == 201, second.text
    cancelled = client.post(
        f"/api/v1/workflow/instances/{second.json()['id']}/cancel",
        headers=headers(collaborator_id),
    )
    assert cancelled.status_code == 200, cancelled.text

    with workflow_db() as session:
        notifications = list(
            session.scalars(
                select(Notification)
                .where(Notification.recipient_user_id == admin_id)
                .order_by(Notification.created_at, Notification.id)
            ).all()
        )
        assert {item.event_code for item in notifications} == {
            "workflow.instance.transitioned",
            "workflow.instance.cancelled",
        }
        assert all(item.organization_id == branch_id for item in notifications)
        assert all(item.action_path == "/?view=workflow" for item in notifications)
