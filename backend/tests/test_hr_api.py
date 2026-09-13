from collections.abc import Iterator
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.access.models import OrganizationScopeMode, Permission, Role, RolePermission, UserRoleAssignment
from app.core.audit.models import AuditEvent
from app.core.identity.models import User
from app.core.identity.security import create_access_token, hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person, PersonOrganizationRelationship
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.hr.models import HREmployment, HRJobProfile, HRPosition
from app.modules.hr.permissions import HR_MANAGE, HR_READ


@pytest.fixture
def hr_db() -> Iterator[sessionmaker[Session]]:
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
def client(hr_db: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        db = hr_db()
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
    scope_mode: OrganizationScopeMode = OrganizationScopeMode.SELF,
    label: str,
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
        password_hash=hash_password("HR-Test-Password-123!"),
    )
    role = Role(code=f"hr-role-{uuid4()}", name="HR role", organization=organization)
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
        session.add_all([holding, company_a, branch_a, company_b])
        session.flush()
        admin = _seed_user(
            session,
            organization=holding,
            permission_codes=(HR_READ, HR_MANAGE),
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
            label="Admin",
        )
        branch_manager = _seed_user(
            session,
            organization=branch_a,
            permission_codes=(HR_READ, HR_MANAGE),
            label="BranchManager",
        )
        company_self_manager = _seed_user(
            session,
            organization=company_a,
            permission_codes=(HR_READ, HR_MANAGE),
            label="CompanySelf",
        )
        outsider = _seed_user(
            session,
            organization=company_b,
            permission_codes=(HR_READ, HR_MANAGE),
            label="Outsider",
        )
        employee = Person(
            first_name="Future",
            last_name="Employee",
            email=f"employee-{uuid4()}@test.local",
        )
        unrelated = Person(
            first_name="Unrelated",
            last_name="Person",
            email=f"unrelated-{uuid4()}@test.local",
        )
        session.add_all([employee, unrelated])
        session.flush()
        session.add(
            PersonOrganizationRelationship(
                person=employee,
                organization=branch_a,
                relationship_code="employee",
            )
        )
        session.commit()
        return {
            "admin": admin.id,
            "branch_manager": branch_manager.id,
            "company_self_manager": company_self_manager.id,
            "outsider": outsider.id,
            "holding": holding.id,
            "company_a": company_a.id,
            "branch_a": branch_a.id,
            "company_b": company_b.id,
            "employee": employee.id,
            "unrelated": unrelated.id,
        }


def _create_profile(
    client: TestClient,
    actor_id,
    organization_id,
    *,
    code: str = "FIN-MGR",
    scope_mode: str = "self_and_descendants",
) -> dict:
    response = client.post(
        "/api/v1/hr/job-profiles",
        headers=headers(actor_id),
        json={
            "organization_id": str(organization_id),
            "code": code,
            "title": "Finance Manager",
            "description": "Reusable future job profile",
            "scope_mode": scope_mode,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_position(
    client: TestClient,
    actor_id,
    organization_id,
    profile_id,
    *,
    code: str,
    reports_to_position_id: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/hr/positions",
        headers=headers(actor_id),
        json={
            "organization_id": str(organization_id),
            "job_profile_id": profile_id,
            "code": code,
            "name": code,
            "reports_to_position_id": reports_to_position_id,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_hr_job_profiles_support_future_structure_and_inheritance(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    inherited = _create_profile(client, ids["admin"], ids["company_a"], code="GEN-MGR")
    _create_profile(
        client,
        ids["admin"],
        ids["company_a"],
        code="COMPANY-ONLY",
        scope_mode="self",
    )

    response = client.get(
        f"/api/v1/hr/job-profiles?organization_id={ids['branch_a']}",
        headers=headers(ids["branch_manager"]),
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [inherited["id"]]

    with hr_db() as session:
        audit = session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "hr.job_profile.created",
                AuditEvent.resource_id == inherited["id"],
            )
        )
        assert audit is not None
        assert audit.organization_id == ids["company_a"]


def test_hr_cross_company_access_is_denied_and_resource_ids_are_hidden(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    profile = _create_profile(client, ids["admin"], ids["company_a"])

    list_response = client.get(
        f"/api/v1/hr/job-profiles?organization_id={ids['company_a']}",
        headers=headers(ids["outsider"]),
    )
    assert list_response.status_code == 403

    guessed_write = client.patch(
        f"/api/v1/hr/job-profiles/{profile['id']}",
        headers=headers(ids["outsider"]),
        json={"title": "Tampered"},
    )
    assert guessed_write.status_code == 404


def test_shared_job_profile_mutation_requires_control_of_impacted_descendant_positions(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    profile = _create_profile(client, ids["admin"], ids["company_a"])
    _create_position(
        client,
        ids["branch_manager"],
        ids["branch_a"],
        profile["id"],
        code="BRANCH-FIN",
    )

    response = client.patch(
        f"/api/v1/hr/job-profiles/{profile['id']}",
        headers=headers(ids["company_self_manager"]),
        json={"title": "Changed centrally"},
    )
    assert response.status_code == 404

    allowed = client.patch(
        f"/api/v1/hr/job-profiles/{profile['id']}",
        headers=headers(ids["admin"]),
        json={"title": "Changed by holding admin"},
    )
    assert allowed.status_code == 200, allowed.text



def test_shared_job_profile_cannot_narrow_scope_while_descendant_position_is_active(
    client: TestClient, hr_db: sessionmaker[Session]
) -> None:
    ids = _seed_tree(hr_db)
    profile = _create_profile(client, ids["admin"], ids["company_a"], code="SHARED")
    position = _create_position(
        client,
        ids["branch_manager"],
        ids["branch_a"],
        profile["id"],
        code="SHARED-SEAT",
    )

    blocked = client.patch(
        f"/api/v1/hr/job-profiles/{profile['id']}",
        headers=headers(ids["admin"]),
        json={"scope_mode": "self"},
    )
    assert blocked.status_code == 409

    deactivated = client.post(
        f"/api/v1/hr/positions/{position['id']}/status",
        headers=headers(ids["branch_manager"]),
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text

    narrowed = client.patch(
        f"/api/v1/hr/job-profiles/{profile['id']}",
        headers=headers(ids["admin"]),
        json={"scope_mode": "self"},
    )
    assert narrowed.status_code == 200, narrowed.text
    assert narrowed.json()["scope_mode"] == "self"


def test_employment_relationship_dates_support_future_planning_without_exposing_not_yet_active_people(
    client: TestClient, hr_db: sessionmaker[Session]
) -> None:
    ids = _seed_tree(hr_db)
    future_start = date.today() + timedelta(days=30)
    day_before = future_start - timedelta(days=1)

    with hr_db() as session:
        future_person = Person(first_name="Future", last_name="Starter")
        session.add(future_person)
        session.flush()
        session.add(
            PersonOrganizationRelationship(
                person=future_person,
                organization=session.get(Organization, ids["branch_a"]),
                relationship_code="employee",
                start_date=future_start,
                is_active=True,
            )
        )
        session.commit()
        future_person_id = future_person.id

    people = client.get(
        f"/api/v1/hr/people?organization_id={ids['branch_a']}",
        headers=headers(ids["branch_manager"]),
    )
    assert people.status_code == 200, people.text
    assert str(future_person_id) not in {item["id"] for item in people.json()}

    too_early = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(future_person_id),
            "employment_number": "FUT-001",
            "employment_type": "fixed_term",
            "start_date": day_before.isoformat(),
        },
    )
    assert too_early.status_code == 400

    planned = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(future_person_id),
            "employment_number": "FUT-001",
            "employment_type": "fixed_term",
            "start_date": future_start.isoformat(),
        },
    )
    assert planned.status_code == 201, planned.text
    assert planned.json()["start_date"] == future_start.isoformat()

def test_position_reporting_cycle_and_deactivation_dependencies_are_blocked(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    profile = _create_profile(client, ids["admin"], ids["branch_a"], scope_mode="self")
    top = _create_position(client, ids["branch_manager"], ids["branch_a"], profile["id"], code="TOP")
    child = _create_position(
        client,
        ids["branch_manager"],
        ids["branch_a"],
        profile["id"],
        code="CHILD",
        reports_to_position_id=top["id"],
    )

    cycle = client.patch(
        f"/api/v1/hr/positions/{top['id']}",
        headers=headers(ids["branch_manager"]),
        json={"reports_to_position_id": child["id"]},
    )
    assert cycle.status_code == 400

    deactivate = client.post(
        f"/api/v1/hr/positions/{top['id']}/status",
        headers=headers(ids["branch_manager"]),
        json={"is_active": False},
    )
    assert deactivate.status_code == 409


def test_employment_requires_existing_person_relationship_and_enforces_single_active_seat(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    profile = _create_profile(client, ids["admin"], ids["branch_a"], scope_mode="self")
    position = _create_position(
        client,
        ids["branch_manager"],
        ids["branch_a"],
        profile["id"],
        code="SEAT-1",
    )

    bad = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(ids["unrelated"]),
            "position_id": position["id"],
            "employment_number": "E-002",
            "employment_type": "permanent",
            "start_date": "2026-09-11",
        },
    )
    assert bad.status_code == 400

    created = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(ids["employee"]),
            "position_id": position["id"],
            "employment_number": "E-001",
            "employment_type": "permanent",
            "start_date": "2026-09-11",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["person"]["first_name"] == "Future"

    duplicate_person = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(ids["employee"]),
            "employment_number": "E-003",
            "employment_type": "other",
            "start_date": "2026-09-11",
        },
    )
    assert duplicate_person.status_code == 409

    with hr_db() as session:
        other = Person(first_name="Second", last_name="Employee")
        session.add(other)
        session.flush()
        session.add(
            PersonOrganizationRelationship(
                person=other,
                organization=session.get(Organization, ids["branch_a"]),
                relationship_code="employee",
            )
        )
        session.commit()
        other_id = other.id

    duplicate_seat = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(other_id),
            "position_id": position["id"],
            "employment_number": "E-004",
            "employment_type": "other",
            "start_date": "2026-09-11",
        },
    )
    assert duplicate_seat.status_code == 409


def test_employment_history_can_end_and_reactivate_without_hard_delete(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    profile = _create_profile(client, ids["admin"], ids["branch_a"], scope_mode="self")
    position = _create_position(client, ids["branch_manager"], ids["branch_a"], profile["id"], code="SEAT")
    created = client.post(
        "/api/v1/hr/employments",
        headers=headers(ids["branch_manager"]),
        json={
            "organization_id": str(ids["branch_a"]),
            "person_id": str(ids["employee"]),
            "position_id": position["id"],
            "employment_number": "HIST-1",
            "employment_type": "fixed_term",
            "start_date": "2026-01-01",
        },
    ).json()

    ended = client.post(
        f"/api/v1/hr/employments/{created['id']}/status",
        headers=headers(ids["branch_manager"]),
        json={"is_active": False, "end_date": "2026-09-11"},
    )
    assert ended.status_code == 200, ended.text
    assert ended.json()["is_active"] is False
    assert ended.json()["end_date"] == "2026-09-11"

    reactivated = client.post(
        f"/api/v1/hr/employments/{created['id']}/status",
        headers=headers(ids["branch_manager"]),
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["is_active"] is True
    assert reactivated.json()["end_date"] is None

    with hr_db() as session:
        rows = session.scalars(select(HREmployment)).all()
        assert len(rows) == 1
        status_audits = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "hr.employment.status.changed")
        ).all()
        assert len(status_audits) == 2


def test_hr_organization_capabilities_do_not_depend_on_organization_read(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    response = client.get("/api/v1/hr/organizations", headers=headers(ids["branch_manager"]))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(ids["branch_a"])
    assert payload[0]["can_read"] is True
    assert payload[0]["can_manage"] is True


def test_hr_write_endpoints_require_authentication(client: TestClient, hr_db: sessionmaker[Session]) -> None:
    ids = _seed_tree(hr_db)
    response = client.post(
        "/api/v1/hr/job-profiles",
        json={
            "organization_id": str(ids["company_a"]),
            "code": "X",
            "title": "X",
            "scope_mode": "self",
        },
    )
    assert response.status_code == 401
