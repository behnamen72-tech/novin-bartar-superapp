from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.core.access.admin_schemas import (
    AccessAssignmentCreateRequest,
    AccessAssignmentItem,
    AccessAssignmentStatusRequest,
    AccessOverviewItem,
    PermissionCatalogItem,
    RoleAdminItem,
    RoleCreateRequest,
    RoleStatusRequest,
    RoleUpdateRequest,
)
from app.core.access.models import (
    OrganizationScopeMode,
    Permission,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.core.access.permissions import ACCESS_MANAGE, ACCESS_READ
from app.core.access.policy import (
    assignment_is_effective_for_organization,
    has_permission,
    organization_is_in_scope,
    require_permission_for_organization,
)
from app.core.access.service import (
    assert_actor_can_delegate_permission_set,
    authorized_organization_ids,
    organization_ids_in_scope,
)
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.organization.models import Organization
from app.core.people.models import PersonOrganizationRelationship


class AccessAdminNotFoundError(LookupError):
    pass


class AccessAdminConflictError(ValueError):
    pass


class AccessAdminValidationError(ValueError):
    pass


def _role_statement(role_id: UUID, *, for_update: bool = False) -> Select[tuple[Role]]:
    statement = (
        select(Role)
        .where(Role.id == role_id)
        .options(
            selectinload(Role.organization),
            selectinload(Role.permission_links).selectinload(RolePermission.permission),
            selectinload(Role.user_assignments).selectinload(UserRoleAssignment.organization),
            selectinload(Role.user_assignments)
            .selectinload(UserRoleAssignment.user)
            .selectinload(User.person),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_role(session: Session, role_id: UUID, *, for_update: bool = False) -> Role:
    role = session.scalar(_role_statement(role_id, for_update=for_update))
    if role is None:
        raise AccessAdminNotFoundError("Role not found.")
    return role


def _get_assignment(
    session: Session,
    assignment_id: UUID,
    *,
    for_update: bool = False,
) -> UserRoleAssignment:
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.id == assignment_id)
        .options(
            selectinload(UserRoleAssignment.organization),
            selectinload(UserRoleAssignment.user).selectinload(User.person),
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    assignment = session.scalar(statement)
    if assignment is None:
        raise AccessAdminNotFoundError("Access assignment not found.")
    return assignment


def _role_permission_codes(role: Role) -> set[str]:
    return {link.permission.code for link in role.permission_links if link.permission.is_active}


def _assignment_is_current_at_root(
    session: Session,
    assignment: UserRoleAssignment,
) -> bool:
    return assignment_is_effective_for_organization(
        session,
        assignment=assignment,
        target_organization_id=assignment.organization_id,
        now=datetime.now(UTC),
    )


def _role_affected_organization_ids(session: Session, role: Role) -> set[UUID]:
    organization_ids: set[UUID] = set()
    if role.organization_id is not None:
        organization_ids.add(role.organization_id)

    for assignment in role.user_assignments:
        if not _assignment_is_current_at_root(session, assignment):
            continue
        organization_ids.update(
            organization_ids_in_scope(
                session,
                scope_organization_id=assignment.organization_id,
                scope_mode=assignment.scope_mode,
            )
        )
    return organization_ids


def _ensure_role_is_runtime_mutable(role: Role) -> None:
    if role.is_system or role.organization_id is None:
        raise AccessAdminConflictError(
            "System and legacy global roles are immutable through the runtime API."
        )


def _assert_actor_can_manage_role(
    session: Session,
    *,
    actor_user_id: UUID,
    role: Role,
    additional_permission_codes: set[str] | None = None,
) -> set[UUID]:
    _ensure_role_is_runtime_mutable(role)
    organization_ids = _role_affected_organization_ids(session, role)
    permission_codes = _role_permission_codes(role)
    if additional_permission_codes:
        permission_codes.update(additional_permission_codes)
    assert_actor_can_delegate_permission_set(
        session,
        actor_user_id=actor_user_id,
        organization_ids=organization_ids,
        permission_codes=permission_codes,
    )
    return organization_ids


def _has_active_person_relationship(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> bool:
    relationship_id = session.scalar(
        select(PersonOrganizationRelationship.id)
        .join(User, User.person_id == PersonOrganizationRelationship.person_id)
        .where(
            User.id == user_id,
            User.is_active.is_(True),
            PersonOrganizationRelationship.organization_id == organization_id,
            PersonOrganizationRelationship.is_active.is_(True),
        )
        .limit(1)
    )
    return relationship_id is not None


def _effective_access_manager_exists(
    session: Session,
    *,
    organization_id: UUID,
    excluded_assignment_id: UUID | None = None,
    excluded_role_id: UUID | None = None,
) -> bool:
    statement = (
        select(UserRoleAssignment)
        .where(UserRoleAssignment.is_active.is_(True))
        .options(
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
            selectinload(UserRoleAssignment.organization),
            selectinload(UserRoleAssignment.user).selectinload(User.person),
        )
    )
    for assignment in session.scalars(statement).all():
        if excluded_assignment_id is not None and assignment.id == excluded_assignment_id:
            continue
        if excluded_role_id is not None and assignment.role_id == excluded_role_id:
            continue
        if not assignment.user.is_active or not assignment.user.person.is_active:
            continue
        if not assignment_is_effective_for_organization(
            session,
            assignment=assignment,
            target_organization_id=organization_id,
        ):
            continue
        if ACCESS_MANAGE in _role_permission_codes(assignment.role):
            return True
    return False


def _ensure_access_manager_survives(
    session: Session,
    *,
    organization_ids: set[UUID],
    excluded_assignment_id: UUID | None = None,
    excluded_role_id: UUID | None = None,
) -> None:
    for organization_id in organization_ids:
        if not _effective_access_manager_exists(
            session,
            organization_id=organization_id,
            excluded_assignment_id=excluded_assignment_id,
            excluded_role_id=excluded_role_id,
        ):
            raise AccessAdminConflictError(
                "Operation would remove the last effective access manager from an organization."
            )


def _role_to_item(role: Role) -> RoleAdminItem:
    return RoleAdminItem(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        organization_id=role.organization_id,
        organization_name=role.organization.name if role.organization is not None else None,
        is_system=role.is_system,
        is_active=role.is_active,
        permissions=sorted(_role_permission_codes(role)),
    )


def _assignment_to_item(assignment: UserRoleAssignment) -> AccessAssignmentItem:
    return AccessAssignmentItem(
        id=assignment.id,
        user_id=assignment.user_id,
        role_id=assignment.role_id,
        role_code=assignment.role.code,
        organization_id=assignment.organization_id,
        organization_name=assignment.organization.name,
        scope_mode=assignment.scope_mode,
        starts_at=assignment.starts_at,
        ends_at=assignment.ends_at,
        is_active=assignment.is_active,
    )


def list_access_overview(
    session: Session,
    *,
    viewer_user_id: UUID,
) -> list[AccessOverviewItem]:
    statement = (
        select(UserRoleAssignment)
        .options(
            selectinload(UserRoleAssignment.organization),
            selectinload(UserRoleAssignment.user).selectinload(User.person),
            selectinload(UserRoleAssignment.role)
            .selectinload(Role.permission_links)
            .selectinload(RolePermission.permission),
        )
        .order_by(UserRoleAssignment.created_at)
    )

    result: list[AccessOverviewItem] = []
    for assignment in session.scalars(statement).all():
        if not has_permission(
            session,
            user_id=viewer_user_id,
            permission_code=ACCESS_READ,
            organization_id=assignment.organization_id,
        ):
            continue
        result.append(
            AccessOverviewItem(
                id=assignment.id,
                user_id=assignment.user_id,
                user_email=assignment.user.email,
                user_name=(
                    f"{assignment.user.person.first_name} {assignment.user.person.last_name}"
                ).strip(),
                role_code=assignment.role.code,
                role_name=assignment.role.name,
                organization_id=assignment.organization_id,
                organization_name=assignment.organization.name,
                scope_mode=assignment.scope_mode,
                is_active=assignment.is_active,
                permissions=sorted(_role_permission_codes(assignment.role)),
            )
        )
    return result


def list_permission_catalog(
    session: Session,
    *,
    viewer_user_id: UUID,
) -> list[PermissionCatalogItem]:
    if not authorized_organization_ids(
        session,
        user_id=viewer_user_id,
        permission_code=ACCESS_READ,
    ):
        return []
    permissions = session.scalars(select(Permission).order_by(Permission.code)).all()
    return [
        PermissionCatalogItem(
            id=permission.id,
            code=permission.code,
            name=permission.name,
            description=permission.description,
            is_active=permission.is_active,
        )
        for permission in permissions
    ]


def list_roles_for_user(
    session: Session,
    *,
    viewer_user_id: UUID,
) -> list[RoleAdminItem]:
    allowed_org_ids = authorized_organization_ids(
        session,
        user_id=viewer_user_id,
        permission_code=ACCESS_READ,
    )
    if not allowed_org_ids:
        return []
    roles = session.scalars(
        select(Role)
        .options(
            selectinload(Role.organization),
            selectinload(Role.permission_links).selectinload(RolePermission.permission),
        )
        .order_by(Role.code)
    ).all()
    return [
        _role_to_item(role)
        for role in roles
        if role.organization_id is None or role.organization_id in allowed_org_ids
    ]


def create_role(
    session: Session,
    *,
    actor: User,
    payload: RoleCreateRequest,
) -> RoleAdminItem:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=ACCESS_MANAGE,
        organization_id=payload.organization_id,
    )
    organization = session.get(Organization, payload.organization_id)
    if organization is None or not organization.is_active:
        raise AccessAdminNotFoundError("Organization not found.")
    if session.scalar(select(Role.id).where(Role.code == payload.code).limit(1)) is not None:
        raise AccessAdminConflictError("Role code already exists.")

    role = Role(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        organization=organization,
        is_system=False,
        is_active=True,
    )
    session.add(role)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action="role.created",
        resource_type="role",
        resource_id=role.id,
        after_state={
            "code": role.code,
            "name": role.name,
            "description": role.description,
            "organization_id": str(organization.id),
            "is_active": True,
        },
    )
    session.commit()
    return _role_to_item(_get_role(session, role.id))


def update_role(
    session: Session,
    *,
    actor: User,
    role_id: UUID,
    payload: RoleUpdateRequest,
) -> RoleAdminItem:
    role = _get_role(session, role_id, for_update=True)
    _assert_actor_can_manage_role(session, actor_user_id=actor.id, role=role)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _role_to_item(role)

    before = {"name": role.name, "description": role.description}
    if "name" in changes:
        role.name = changes["name"]
    if "description" in changes:
        role.description = changes["description"]
    after = {"name": role.name, "description": role.description}
    if before == after:
        return _role_to_item(role)

    assert role.organization_id is not None
    record_audit_event(
        session,
        actor=actor,
        organization_id=role.organization_id,
        action="role.updated",
        resource_type="role",
        resource_id=role.id,
        before_state=before,
        after_state=after,
    )
    session.commit()
    return _role_to_item(_get_role(session, role.id))


def change_role_status(
    session: Session,
    *,
    actor: User,
    role_id: UUID,
    payload: RoleStatusRequest,
) -> RoleAdminItem:
    role = _get_role(session, role_id, for_update=True)
    affected_ids = _assert_actor_can_manage_role(
        session,
        actor_user_id=actor.id,
        role=role,
    )
    if role.is_active is payload.is_active:
        return _role_to_item(role)
    if not payload.is_active and ACCESS_MANAGE in _role_permission_codes(role):
        _ensure_access_manager_survives(
            session,
            organization_ids=affected_ids,
            excluded_role_id=role.id,
        )

    before = {"is_active": role.is_active}
    role.is_active = payload.is_active
    assert role.organization_id is not None
    record_audit_event(
        session,
        actor=actor,
        organization_id=role.organization_id,
        action="role.status.changed",
        resource_type="role",
        resource_id=role.id,
        before_state=before,
        after_state={"is_active": role.is_active},
    )
    session.commit()
    return _role_to_item(_get_role(session, role.id))


def grant_permission_to_role(
    session: Session,
    *,
    actor: User,
    role_id: UUID,
    permission_code: str,
) -> RoleAdminItem:
    role = _get_role(session, role_id, for_update=True)
    normalized_code = permission_code.strip().lower()
    permission = session.scalar(
        select(Permission).where(Permission.code == normalized_code, Permission.is_active.is_(True))
    )
    if permission is None:
        raise AccessAdminNotFoundError("Permission not found.")
    _assert_actor_can_manage_role(
        session,
        actor_user_id=actor.id,
        role=role,
        additional_permission_codes={permission.code},
    )
    if any(link.permission_id == permission.id for link in role.permission_links):
        return _role_to_item(role)

    role.permission_links.append(RolePermission(permission=permission))
    assert role.organization_id is not None
    record_audit_event(
        session,
        actor=actor,
        organization_id=role.organization_id,
        action="permission.granted",
        resource_type="role",
        resource_id=role.id,
        after_state={"permission_code": permission.code},
    )
    session.commit()
    return _role_to_item(_get_role(session, role.id))


def revoke_permission_from_role(
    session: Session,
    *,
    actor: User,
    role_id: UUID,
    permission_code: str,
) -> RoleAdminItem:
    role = _get_role(session, role_id, for_update=True)
    affected_ids = _assert_actor_can_manage_role(
        session,
        actor_user_id=actor.id,
        role=role,
    )
    normalized_code = permission_code.strip().lower()
    link = next(
        (item for item in role.permission_links if item.permission.code == normalized_code),
        None,
    )
    if link is None:
        raise AccessAdminNotFoundError("Role permission not found.")
    if normalized_code == ACCESS_MANAGE:
        _ensure_access_manager_survives(
            session,
            organization_ids=affected_ids,
            excluded_role_id=role.id,
        )

    role.permission_links.remove(link)
    session.delete(link)
    assert role.organization_id is not None
    record_audit_event(
        session,
        actor=actor,
        organization_id=role.organization_id,
        action="permission.revoked",
        resource_type="role",
        resource_id=role.id,
        before_state={"permission_code": normalized_code},
    )
    session.commit()
    return _role_to_item(_get_role(session, role.id))


def create_access_assignment(
    session: Session,
    *,
    actor: User,
    payload: AccessAssignmentCreateRequest,
) -> AccessAssignmentItem:
    role = _get_role(session, payload.role_id)
    if not role.is_active:
        raise AccessAdminConflictError("Cannot assign an inactive role.")
    organization = session.get(Organization, payload.organization_id)
    if organization is None or not organization.is_active:
        raise AccessAdminNotFoundError("Organization not found.")
    target_user = session.scalar(
        select(User).where(User.id == payload.user_id).options(selectinload(User.person))
    )
    if target_user is None or not target_user.is_active or not target_user.person.is_active:
        raise AccessAdminNotFoundError("User not found.")
    if not _has_active_person_relationship(
        session,
        user_id=target_user.id,
        organization_id=organization.id,
    ):
        raise AccessAdminValidationError(
            "Target user must have an active person relationship with the assignment organization."
        )

    if role.organization_id is not None and not organization_is_in_scope(
        session,
        scope_organization_id=role.organization_id,
        scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
        target_organization_id=organization.id,
    ):
        raise AccessAdminValidationError(
            "Organization-owned role cannot be assigned outside its owner organization subtree."
        )

    covered_ids = organization_ids_in_scope(
        session,
        scope_organization_id=organization.id,
        scope_mode=payload.scope_mode,
    )
    assert_actor_can_delegate_permission_set(
        session,
        actor_user_id=actor.id,
        organization_ids=covered_ids,
        permission_codes=_role_permission_codes(role),
    )

    existing = session.scalar(
        select(UserRoleAssignment)
        .where(
            UserRoleAssignment.user_id == target_user.id,
            UserRoleAssignment.role_id == role.id,
            UserRoleAssignment.organization_id == organization.id,
            UserRoleAssignment.scope_mode == payload.scope_mode,
        )
        .with_for_update()
    )
    if existing is not None:
        if existing.is_active:
            raise AccessAdminConflictError("Matching active access assignment already exists.")
        existing.is_active = True
        existing.starts_at = payload.starts_at
        existing.ends_at = payload.ends_at
        assignment = existing
        action = "role.assignment.reactivated"
    else:
        assignment = UserRoleAssignment(
            user=target_user,
            role=role,
            organization=organization,
            scope_mode=payload.scope_mode,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            is_active=True,
        )
        session.add(assignment)
        session.flush()
        action = "role.assigned"

    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action=action,
        resource_type="user_role_assignment",
        resource_id=assignment.id,
        after_state={
            "user_id": str(target_user.id),
            "role_id": str(role.id),
            "role_code": role.code,
            "scope_mode": payload.scope_mode.value,
            "starts_at": payload.starts_at.isoformat() if payload.starts_at else None,
            "ends_at": payload.ends_at.isoformat() if payload.ends_at else None,
            "is_active": True,
        },
    )
    session.commit()
    return _assignment_to_item(_get_assignment(session, assignment.id))


def change_access_assignment_status(
    session: Session,
    *,
    actor: User,
    assignment_id: UUID,
    payload: AccessAssignmentStatusRequest,
) -> AccessAssignmentItem:
    assignment = _get_assignment(session, assignment_id, for_update=True)
    covered_ids = organization_ids_in_scope(
        session,
        scope_organization_id=assignment.organization_id,
        scope_mode=assignment.scope_mode,
    )
    role_permissions = _role_permission_codes(assignment.role)
    assert_actor_can_delegate_permission_set(
        session,
        actor_user_id=actor.id,
        organization_ids=covered_ids,
        permission_codes=role_permissions,
    )
    if assignment.is_active is payload.is_active:
        return _assignment_to_item(assignment)

    if payload.is_active:
        if not assignment.role.is_active:
            raise AccessAdminConflictError("Cannot reactivate an assignment for an inactive role.")
        if not assignment.user.is_active or not assignment.user.person.is_active:
            raise AccessAdminConflictError("Cannot reactivate access for an inactive user/person.")
        if not _has_active_person_relationship(
            session,
            user_id=assignment.user_id,
            organization_id=assignment.organization_id,
        ):
            raise AccessAdminConflictError(
                "Cannot reactivate access without an active person relationship "
                "at the assignment organization."
            )
        if assignment.role.organization_id is not None and not organization_is_in_scope(
            session,
            scope_organization_id=assignment.role.organization_id,
            scope_mode=OrganizationScopeMode.SELF_AND_DESCENDANTS,
            target_organization_id=assignment.organization_id,
        ):
            raise AccessAdminConflictError(
                "Role ownership no longer covers the assignment organization."
            )

    if (
        not payload.is_active
        and ACCESS_MANAGE in role_permissions
        and _assignment_is_current_at_root(session, assignment)
    ):
        _ensure_access_manager_survives(
            session,
            organization_ids=covered_ids,
            excluded_assignment_id=assignment.id,
        )

    before = {"is_active": assignment.is_active}
    assignment.is_active = payload.is_active
    record_audit_event(
        session,
        actor=actor,
        organization_id=assignment.organization_id,
        action="role.assignment.status.changed",
        resource_type="user_role_assignment",
        resource_id=assignment.id,
        before_state=before,
        after_state={"is_active": assignment.is_active},
        metadata={
            "user_id": str(assignment.user_id),
            "role_id": str(assignment.role_id),
            "role_code": assignment.role.code,
            "scope_mode": assignment.scope_mode.value,
        },
    )
    session.commit()
    return _assignment_to_item(_get_assignment(session, assignment.id))
