from datetime import UTC, datetime, timedelta

import pytest
from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.access.policy import (
    AuthorizationError,
    has_permission,
    require_permission_for_organization,
)
from app.core.identity.models import User
from app.core.identity.security import hash_password
from app.core.organization.models import Organization, OrganizationType
from app.core.people.models import Person
from app.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def make_graph(session: Session):
    holding = Organization(name="Holding", code="H", organization_type=OrganizationType.HOLDING)
    company_a = Organization(
        name="Company A", code="A", organization_type=OrganizationType.COMPANY, parent=holding
    )
    branch_a = Organization(
        name="Branch A", code="A-B", organization_type=OrganizationType.BRANCH, parent=company_a
    )
    company_b = Organization(
        name="Company B", code="B", organization_type=OrganizationType.COMPANY, parent=holding
    )
    person = Person(first_name="Access", last_name="User", email="access@example.com")
    user = User(
        person=person,
        email="access@example.com",
        username="accessuser",
        password_hash=hash_password("Strong-password-123!"),
    )
    permission = Permission(code="people.read", name="Read people")
    role = Role(code="company_reader", name="Company Reader")
    role.permission_links.append(RolePermission(permission=permission))
    session.add_all([holding, company_a, branch_a, company_b, person, user, permission, role])
    session.flush()
    return holding, company_a, branch_a, company_b, user, role


def test_deny_by_default() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _, company_a, _, _, user, _ = make_graph(session)
        assert (
            has_permission(
                session,
                user_id=user.id,
                permission_code="people.read",
                organization_id=company_a.id,
            )
            is False
        )


def test_self_scope_allows_only_exact_organization() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _, company_a, branch_a, _, user, role = make_graph(session)
        session.add(
            UserRoleAssignment(
                user=user, role=role, organization=company_a, scope_mode=OrganizationScopeMode.SELF
            )
        )
        session.flush()
        assert (
            has_permission(
                session,
                user_id=user.id,
                permission_code="people.read",
                organization_id=company_a.id,
            )
            is True
        )
        assert (
            has_permission(
                session, user_id=user.id, permission_code="people.read", organization_id=branch_a.id
            )
            is False
        )


def test_descendant_scope_allows_children_but_not_sibling_company() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _, company_a, branch_a, company_b, user, role = make_graph(session)
        session.add(
            UserRoleAssignment(
                user=user,
                role=role,
                organization=company_a,
                scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
            )
        )
        session.flush()
        assert (
            has_permission(
                session, user_id=user.id, permission_code="people.read", organization_id=branch_a.id
            )
            is True
        )
        assert (
            has_permission(
                session,
                user_id=user.id,
                permission_code="people.read",
                organization_id=company_b.id,
            )
            is False
        )


def test_inactive_role_or_expired_assignment_denies() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _, company_a, _, _, user, role = make_graph(session)
        assignment = UserRoleAssignment(
            user=user,
            role=role,
            organization=company_a,
            scope_mode=OrganizationScopeMode.SELF,
            ends_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        session.add(assignment)
        session.flush()
        assert (
            has_permission(
                session,
                user_id=user.id,
                permission_code="people.read",
                organization_id=company_a.id,
            )
            is False
        )

        assignment.ends_at = None
        role.is_active = False
        session.flush()
        assert (
            has_permission(
                session,
                user_id=user.id,
                permission_code="people.read",
                organization_id=company_a.id,
            )
            is False
        )


def test_missing_permission_denies_even_with_role_assignment() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _, company_a, _, _, user, role = make_graph(session)
        session.add(
            UserRoleAssignment(
                user=user, role=role, organization=company_a, scope_mode=OrganizationScopeMode.SELF
            )
        )
        session.flush()
        assert (
            has_permission(
                session,
                user_id=user.id,
                permission_code="people.manage",
                organization_id=company_a.id,
            )
            is False
        )

        with pytest.raises(AuthorizationError):
            require_permission_for_organization(
                session,
                user_id=user.id,
                permission_code="people.manage",
                organization_id=company_a.id,
            )
