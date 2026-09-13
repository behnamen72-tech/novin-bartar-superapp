from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.access.models import OrganizationScopeMode, Role, RolePermission, UserRoleAssignment
from app.core.organization.models import Organization


class AuthorizationError(PermissionError):
    pass


def _is_assignment_current(assignment: UserRoleAssignment, now: datetime) -> bool:
    if not assignment.is_active or not assignment.role.is_active:
        return False
    if assignment.starts_at is not None and assignment.starts_at > now:
        return False
    if assignment.ends_at is not None and assignment.ends_at <= now:
        return False
    return True


def _organization_is_in_scope(
    session: Session,
    *,
    scope_organization_id: UUID,
    scope_mode: OrganizationScopeMode,
    target_organization_id: UUID,
    require_target_active: bool = True,
) -> bool:
    if scope_organization_id == target_organization_id:
        return True

    if scope_mode is OrganizationScopeMode.SELF:
        return False

    target = session.get(Organization, target_organization_id)
    if target is None or (require_target_active and not target.is_active):
        return False

    visited: set[UUID] = set()
    current = target

    while current.parent_id is not None:
        if current.id in visited:
            return False
        visited.add(current.id)

        if current.parent_id == scope_organization_id:
            scope_org = session.get(Organization, scope_organization_id)
            return scope_org is not None and scope_org.is_active

        parent = current.parent
        if parent is None:
            parent = session.get(Organization, current.parent_id)
        if parent is None or not parent.is_active:
            return False
        current = parent

    return False



def organization_is_in_scope(
    session: Session,
    *,
    scope_organization_id: UUID,
    scope_mode: OrganizationScopeMode,
    target_organization_id: UUID,
) -> bool:
    """Public canonical organization-scope check for Core administration."""
    return _organization_is_in_scope(
        session,
        scope_organization_id=scope_organization_id,
        scope_mode=scope_mode,
        target_organization_id=target_organization_id,
    )

def assignment_is_effective_for_organization(
    session: Session,
    *,
    assignment: UserRoleAssignment,
    target_organization_id: UUID,
    now: datetime | None = None,
) -> bool:
    """Return whether an assignment is currently effective for a target org.

    This is the shared scope/time/activity primitive for Core services that need
    to reason about the exact role that grants access, not just a boolean
    permission result. Keeping it here prevents document-level ACLs from
    inventing a second organization-scope implementation.
    """
    target_org = session.get(Organization, target_organization_id)
    if target_org is None or not target_org.is_active:
        return False

    effective_now = now or datetime.now(UTC)
    if not _is_assignment_current(assignment, effective_now):
        return False

    return _organization_is_in_scope(
        session,
        scope_organization_id=assignment.organization_id,
        scope_mode=assignment.scope_mode,
        target_organization_id=target_organization_id,
    )


def has_permission(
    session: Session,
    *,
    user_id: UUID,
    permission_code: str,
    organization_id: UUID,
) -> bool:
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.user_id == user_id)
        .options(
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission)
        )
    )
    assignments = list(session.scalars(statement).all())
    now = datetime.now(UTC)

    for assignment in assignments:
        if not assignment_is_effective_for_organization(
            session,
            assignment=assignment,
            target_organization_id=organization_id,
            now=now,
        ):
            continue

        permission_codes = {
            link.permission.code
            for link in assignment.role.permission_links
            if link.permission.is_active
        }
        if permission_code in permission_codes:
            return True

    return False



def has_permission_including_inactive_target(
    session: Session,
    *,
    user_id: UUID,
    permission_code: str,
    organization_id: UUID,
) -> bool:
    """Authorize reactivation of an inactive org without weakening normal B3 checks.

    Only the target itself may be inactive; the assignment organization and every
    ancestor traversed by the scope rule must remain active.
    """
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
    for assignment in session.scalars(statement).all():
        if not _is_assignment_current(assignment, now):
            continue
        if not assignment.organization.is_active:
            continue
        if not _organization_is_in_scope(
            session,
            scope_organization_id=assignment.organization_id,
            scope_mode=assignment.scope_mode,
            target_organization_id=organization_id,
            require_target_active=False,
        ):
            continue
        if any(
            link.permission.is_active and link.permission.code == permission_code
            for link in assignment.role.permission_links
        ):
            return True
    return False

def require_permission_for_organization(
    session: Session,
    *,
    user_id: UUID,
    permission_code: str,
    organization_id: UUID,
) -> None:
    if not has_permission(
        session,
        user_id=user_id,
        permission_code=permission_code,
        organization_id=organization_id,
    ):
        raise AuthorizationError("Permission denied.")
