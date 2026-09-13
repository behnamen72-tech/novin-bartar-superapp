from collections.abc import Iterator
from uuid import uuid4

import pytest
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.notifications.events import NotificationIntegrityError
from app.core.notifications.models import Notification, NotificationSeverity
from app.core.notifications.service import NotificationValidationError, create_notification
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def notification_db() -> Iterator[sessionmaker[Session]]:
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
def client(notification_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = notification_db()
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


def _seed_user(session: Session, label: str) -> User:
    email = f"{label.lower()}-{uuid4()}@test.local"
    person = Person(first_name=label, last_name="User", email=email)
    user = User(
        person=person,
        email=email,
        username=f"{label.lower()}-{uuid4()}",
        password_hash=hash_password("Notification-Test-Password-123!"),
    )
    session.add_all([person, user])
    session.flush()
    return user


def _seed(factory: sessionmaker[Session]):
    with factory() as session:
        organization = Organization(
            name="Notification Org",
            code=f"NOTIFY-{uuid4()}",
            organization_type=OrganizationType.HOLDING,
        )
        first = _seed_user(session, "First")
        second = _seed_user(session, "Second")
        session.add(organization)
        session.flush()
        first_notification = create_notification(
            session,
            recipient_user_id=first.id,
            organization_id=organization.id,
            event_code="document.expiring",
            source="documents",
            severity=NotificationSeverity.WARNING,
            title="Document expires soon",
            body="Review the document before expiration.",
            resource_type="document",
            resource_id=str(uuid4()),
            action_path="/?view=documents",
            dedupe_key="doc-expiring-1",
        )
        second_notification = create_notification(
            session,
            recipient_user_id=second.id,
            event_code="workflow.changed",
            source="workflow",
            title="Workflow updated",
            dedupe_key="workflow-1",
        )
        session.commit()
        return first.id, second.id, organization.id, first_notification.id, second_notification.id


def _headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_notifications_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/notifications").status_code == 401
    assert client.get("/api/v1/notifications/unread-count").status_code == 401
    assert client.post(f"/api/v1/notifications/{uuid4()}/read").status_code == 401


def test_recipient_can_list_without_b3_role_and_other_user_is_hidden(
    client: TestClient,
    notification_db: sessionmaker[Session],
) -> None:
    first_id, second_id, _, first_notification_id, second_notification_id = _seed(notification_db)

    response = client.get("/api/v1/notifications", headers=_headers(first_id))
    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [str(first_notification_id)]
    assert items[0]["severity"] == "warning"
    assert items[0]["action_path"] == "/?view=documents"

    hidden = client.get(
        f"/api/v1/notifications/{second_notification_id}",
        headers=_headers(first_id),
    )
    assert hidden.status_code == 404

    visible = client.get(
        f"/api/v1/notifications/{second_notification_id}",
        headers=_headers(second_id),
    )
    assert visible.status_code == 200


def test_read_unread_and_unread_count_are_recipient_scoped(
    client: TestClient,
    notification_db: sessionmaker[Session],
) -> None:
    first_id, second_id, _, first_notification_id, _ = _seed(notification_db)

    count = client.get("/api/v1/notifications/unread-count", headers=_headers(first_id))
    assert count.status_code == 200
    assert count.json() == {"unread_count": 1}

    read = client.post(
        f"/api/v1/notifications/{first_notification_id}/read",
        headers=_headers(first_id),
    )
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    assert client.get("/api/v1/notifications?unread_only=true", headers=_headers(first_id)).json() == []
    assert client.get("/api/v1/notifications/unread-count", headers=_headers(first_id)).json() == {"unread_count": 0}

    unread = client.post(
        f"/api/v1/notifications/{first_notification_id}/unread",
        headers=_headers(first_id),
    )
    assert unread.status_code == 200
    assert unread.json()["read_at"] is None

    forbidden_by_ownership = client.post(
        f"/api/v1/notifications/{first_notification_id}/read",
        headers=_headers(second_id),
    )
    assert forbidden_by_ownership.status_code == 404


def test_mark_all_read_only_updates_current_recipient(
    client: TestClient,
    notification_db: sessionmaker[Session],
) -> None:
    first_id, second_id, organization_id, _, _ = _seed(notification_db)
    with notification_db() as session:
        create_notification(
            session,
            recipient_user_id=first_id,
            organization_id=organization_id,
            event_code="second",
            title="Second notification",
        )
        session.commit()

    response = client.post("/api/v1/notifications/read-all", headers=_headers(first_id))
    assert response.status_code == 200
    assert response.json() == {"marked_read": 2}
    assert client.get("/api/v1/notifications/unread-count", headers=_headers(first_id)).json() == {"unread_count": 0}
    assert client.get("/api/v1/notifications/unread-count", headers=_headers(second_id)).json() == {"unread_count": 1}


def test_internal_creation_is_idempotent_and_transactional(
    notification_db: sessionmaker[Session],
) -> None:
    with notification_db() as session:
        organization = Organization(
            name="Org",
            code=f"ORG-{uuid4()}",
            organization_type=OrganizationType.HOLDING,
        )
        user = _seed_user(session, "Producer")
        session.add(organization)
        session.flush()
        first = create_notification(
            session,
            recipient_user_id=user.id,
            organization_id=organization.id,
            event_code="task.assigned",
            title="Task assigned",
            dedupe_key="task-42-assigned",
        )
        duplicate = create_notification(
            session,
            recipient_user_id=user.id,
            organization_id=organization.id,
            event_code="task.assigned",
            title="Task assigned",
            dedupe_key="task-42-assigned",
        )
        assert first.id == duplicate.id
        user_id = user.id
        session.rollback()

    with notification_db() as session:
        assert session.scalar(select(Notification.id).where(Notification.recipient_user_id == user_id)) is None


def test_notification_content_is_immutable_but_read_state_can_change(
    notification_db: sessionmaker[Session],
) -> None:
    first_id, _, _, first_notification_id, _ = _seed(notification_db)
    with notification_db() as session:
        notification = session.get(Notification, first_notification_id)
        assert notification is not None
        notification.title = "Tampered"
        with pytest.raises(NotificationIntegrityError):
            session.flush()
        session.rollback()

        notification = session.get(Notification, first_notification_id)
        assert notification is not None
        notification.read_at = notification.created_at
        session.flush()
        session.rollback()

        notification = session.get(Notification, first_notification_id)
        assert notification is not None
        session.delete(notification)
        with pytest.raises(NotificationIntegrityError):
            session.flush()


def test_notification_rejects_unsafe_action_paths_and_allows_inactive_recipient(
    notification_db: sessionmaker[Session],
) -> None:
    with notification_db() as session:
        user = _seed_user(session, "Safety")
        with pytest.raises(NotificationValidationError):
            create_notification(
                session,
                recipient_user_id=user.id,
                event_code="unsafe",
                title="Unsafe",
                action_path="https://evil.example/path",
            )
        with pytest.raises(NotificationValidationError):
            create_notification(
                session,
                recipient_user_id=user.id,
                event_code="unsafe-backslash",
                title="Unsafe",
                action_path="/\\evil.example/path",
            )
        with pytest.raises(NotificationValidationError):
            create_notification(
                session,
                recipient_user_id=user.id,
                event_code="incomplete-resource",
                title="Incomplete",
                resource_type="document",
            )
        session.rollback()

    with notification_db() as session:
        user = _seed_user(session, "Inactive")
        session.flush()
        user.is_active = False
        session.flush()
        notification = create_notification(
            session,
            recipient_user_id=user.id,
            event_code="inactive",
            title="Inactive recipient history",
        )
        assert notification.recipient_user_id == user.id


def test_notification_filters_are_recipient_scoped(
    client: TestClient,
    notification_db: sessionmaker[Session],
) -> None:
    first_id, _, organization_id, _, _ = _seed(notification_db)
    response = client.get(
        f"/api/v1/notifications?organization_id={organization_id}&event_code=document.expiring",
        headers=_headers(first_id),
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

    missing = client.get(
        f"/api/v1/notifications?organization_id={uuid4()}",
        headers=_headers(first_id),
    )
    assert missing.status_code == 200
    assert missing.json() == []
