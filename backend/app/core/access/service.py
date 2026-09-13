from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.access.models import OrganizationScopeMode, Role, RolePermission, UserRoleAssignment
from app.core.access.policy import (
    assignment_is_effective_for_organization,
    has_permission,
    has_permission_including_inactive_target,
    organization_is_in_scope,
)
from app.core.access.schemas import MyAccessAssignmentResponse
from app.core.identity.models import User
from app.core.organization.models import Organization


def list_effective_assignments(
    session: Session,
    *,
    user_id: UUID,
) -> list[MyAccessAssignmentResponse]:
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.user_id == user_id)
        .options(
            selectinload(UserRoleAssignment.organization),
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
        )
    )

    now = datetime.now(UTC)
    result: list[MyAccessAssignmentResponse] = []

    for assignment in session.scalars(statement).all():
        if not assignment.is_active or not assignment.role.is_active:
            continue
        if not assignment.organization.is_active:
            continue
        if assignment.starts_at is not None and assignment.starts_at > now:
            continue
        if assignment.ends_at is not None and assignment.ends_at <= now:
            continue

        permissions = sorted(
            link.permission.code
            for link in assignment.role.permission_links
            if link.permission.is_active
        )
        result.append(
            MyAccessAssignmentResponse(
                role_code=assignment.role.code,
                organization_id=assignment.organization_id,
                organization_name=assignment.organization.name,
                scope_mode=assignment.scope_mode,
                permissions=permissions,
            )
        )

    return result


def list_authorized_organizations(
    session: Session,
    *,
    user_id: UUID,
    permission_code: str,
) -> list[Organization]:
    organizations = list(
        session.scalars(
            select(Organization).order_by(Organization.name)
        ).all()
    )

    return [
        organization
        for organization in organizations
        if has_permission(
            session,
            user_id=user_id,
            permission_code=permission_code,
            organization_id=organization.id,
        )
    ]


def list_visible_organizations_for_management(
    session: Session,
    *,
    user_id: UUID,
    read_permission_code: str,
    manage_permission_code: str,
) -> list[Organization]:
    """Return readable active orgs plus inactive orgs recoverable by a manager.

    Normal read semantics stay unchanged. This helper exists for operational
    organization-management UIs so an authorized ancestor manager can still
    see and reactivate an inactive descendant. It never broadens management
    scope: inactive rows are included only when the canonical B3
    ``has_permission_including_inactive_target`` check succeeds.
    """
    organizations = list(
        session.scalars(select(Organization).order_by(Organization.name)).all()
    )

    result: list[Organization] = []
    for organization in organizations:
        if organization.is_active and has_permission(
            session,
            user_id=user_id,
            permission_code=read_permission_code,
            organization_id=organization.id,
        ):
            result.append(organization)
            continue

        if has_permission_including_inactive_target(
            session,
            user_id=user_id,
            permission_code=manage_permission_code,
            organization_id=organization.id,
        ):
            result.append(organization)

    return result


def authorized_organization_ids(
    session: Session,
    *,
    user_id: UUID,
    permission_code: str,
) -> set[UUID]:
    return {
        organization.id
        for organization in list_authorized_organizations(
            session,
            user_id=user_id,
            permission_code=permission_code,
        )
    }


def effective_role_ids_for_permission(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    permission_code: str,
) -> set[UUID]:
    """Return the exact active roles that grant a permission for one org."""
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.user_id == user_id)
        .options(
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
            selectinload(UserRoleAssignment.organization),
        )
    )
    now = datetime.now(UTC)
    role_ids: set[UUID] = set()

    for assignment in session.scalars(statement).all():
        if not assignment_is_effective_for_organization(
            session,
            assignment=assignment,
            target_organization_id=organization_id,
            now=now,
        ):
            continue
        if any(
            link.permission.is_active and link.permission.code == permission_code
            for link in assignment.role.permission_links
        ):
            role_ids.add(assignment.role_id)

    return role_ids


def role_has_effective_assignment_for_organization(
    session: Session,
    *,
    role_id: UUID,
    organization_id: UUID,
) -> bool:
    """Return whether a role is currently assigned anywhere in an org scope."""
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.role_id == role_id)
        .options(
            selectinload(UserRoleAssignment.role),
            selectinload(UserRoleAssignment.organization),
            selectinload(UserRoleAssignment.user).selectinload(User.person),
        )
    )
    now = datetime.now(UTC)
    return any(
        assignment.user.is_active
        and assignment.user.person.is_active
        and assignment_is_effective_for_organization(
            session,
            assignment=assignment,
            target_organization_id=organization_id,
            now=now,
        )
        for assignment in session.scalars(statement).all()
    )


def effective_permission_codes_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> set[str]:
    """Return all current active permission codes for a user in one organization."""
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.user_id == user_id)
        .options(
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
            selectinload(UserRoleAssignment.organization),
        )
    )
    now = datetime.now(UTC)
    result: set[str] = set()
    for assignment in session.scalars(statement).all():
        if not assignment_is_effective_for_organization(
            session,
            assignment=assignment,
            target_organization_id=organization_id,
            now=now,
        ):
            continue
        result.update(
            link.permission.code
            for link in assignment.role.permission_links
            if link.permission.is_active
        )
    return result


def organization_ids_in_scope(
    session: Session,
    *,
    scope_organization_id: UUID,
    scope_mode: OrganizationScopeMode,
) -> set[UUID]:
    """Return active organizations covered by one scope using canonical B3 semantics."""
    organizations = session.scalars(
        select(Organization).where(Organization.is_active.is_(True))
    ).all()
    return {
        organization.id
        for organization in organizations
        if organization_is_in_scope(
            session,
            scope_organization_id=scope_organization_id,
            scope_mode=scope_mode,
            target_organization_id=organization.id,
        )
    }


def assert_actor_can_delegate_permission_set(
    session: Session,
    *,
    actor_user_id: UUID,
    organization_ids: set[UUID],
    permission_codes: set[str],
) -> None:
    """Fail closed unless actor can manage access and owns every delegated capability.

    This is the B5.6 privilege-escalation boundary. Permission delegation is
    capability-based rather than relying on brittle numeric role levels.
    """
    from app.core.access.permissions import ACCESS_MANAGE
    from app.core.access.policy import AuthorizationError

    if not organization_ids:
        raise AuthorizationError("Permission denied.")

    for organization_id in organization_ids:
        if not has_permission(
            session,
            user_id=actor_user_id,
            permission_code=ACCESS_MANAGE,
            organization_id=organization_id,
        ):
            raise AuthorizationError("Permission denied.")
        actor_permissions = effective_permission_codes_for_user(
            session,
            user_id=actor_user_id,
            organization_id=organization_id,
        )
        if not permission_codes.issubset(actor_permissions):
            raise AuthorizationError("Permission denied.")


def assert_actor_dominates_user_access(
    session: Session,
    *,
    actor_user_id: UUID,
    target_user_id: UUID,
) -> None:
    """Prevent identity administration from becoming a privilege-escalation path."""
    statement = (
        select(UserRoleAssignment)
        .where(
            UserRoleAssignment.user_id == target_user_id,
            UserRoleAssignment.is_active.is_(True),
        )
        .options(
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
            selectinload(UserRoleAssignment.organization),
        )
    )
    assignments = list(session.scalars(statement).all())
    now = datetime.now(UTC)
    for assignment in assignments:
        if not assignment_is_effective_for_organization(
            session,
            assignment=assignment,
            target_organization_id=assignment.organization_id,
            now=now,
        ):
            continue
        covered_ids = organization_ids_in_scope(
            session,
            scope_organization_id=assignment.organization_id,
            scope_mode=assignment.scope_mode,
        )
        role_permissions = {
            link.permission.code
            for link in assignment.role.permission_links
            if link.permission.is_active
        }
        assert_actor_can_delegate_permission_set(
            session,
            actor_user_id=actor_user_id,
            organization_ids=covered_ids,
            permission_codes=role_permissions,
        )
