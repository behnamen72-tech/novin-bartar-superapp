from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.access.permissions import ORGANIZATION_MANAGE, ORGANIZATION_READ
from app.core.access.service import authorized_organization_ids
from app.core.access.policy import (
    AuthorizationError,
    has_permission_including_inactive_target,
    require_permission_for_organization,
)
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.organization.models import Organization, OrganizationType
from app.core.organization.schemas import (
    OrganizationCreateRequest,
    OrganizationStatusRequest,
    OrganizationUpdateRequest,
)


class OrganizationNotFoundError(LookupError):
    pass


class OrganizationConflictError(ValueError):
    pass


class OrganizationValidationError(ValueError):
    pass


def _get_locked_organization(session: Session, organization_id: UUID) -> Organization:
    organization = session.scalar(
        select(Organization)
        .where(Organization.id == organization_id)
        .with_for_update()
    )
    if organization is None:
        raise OrganizationNotFoundError("Organization not found.")
    return organization


def _code_exists(
    session: Session,
    *,
    code: str,
    exclude_organization_id: UUID | None = None,
) -> bool:
    statement = select(Organization.id).where(Organization.code == code)
    if exclude_organization_id is not None:
        statement = statement.where(Organization.id != exclude_organization_id)
    return session.scalar(statement.limit(1)) is not None


def create_organization(
    session: Session,
    *,
    actor: User,
    payload: OrganizationCreateRequest,
) -> Organization:
    # Creating a second/root holding has no existing organization boundary to
    # authorize against. Root holdings therefore remain bootstrap-only.
    if payload.organization_type is OrganizationType.HOLDING:
        raise OrganizationValidationError(
            "Holding creation is bootstrap-only and is not exposed through the API."
        )

    parent = _get_locked_organization(session, payload.parent_id)
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=ORGANIZATION_MANAGE,
        organization_id=parent.id,
    )
    if not parent.is_active:
        raise OrganizationConflictError("Parent organization is inactive.")
    if _code_exists(session, code=payload.code):
        raise OrganizationConflictError("Organization code already exists.")

    organization = Organization(
        name=payload.name,
        code=payload.code,
        organization_type=payload.organization_type,
        parent=parent,
        is_active=True,
    )
    session.add(organization)

    # Flush invokes the existing B1 hierarchy validator. Requiring permission
    # against the newly-created descendant also proves the actor has a scope
    # that actually covers descendants rather than SELF-only management.
    try:
        session.flush()
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=ORGANIZATION_MANAGE,
            organization_id=organization.id,
        )
    except (AuthorizationError, ValueError):
        session.rollback()
        raise

    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action="organization.created",
        resource_type="organization",
        resource_id=organization.id,
        after_state={
            "name": organization.name,
            "code": organization.code,
            "organization_type": organization.organization_type.value,
            "parent_id": str(organization.parent_id),
            "is_active": organization.is_active,
        },
    )
    session.commit()
    session.refresh(organization)
    return organization


def update_organization(
    session: Session,
    *,
    actor: User,
    organization_id: UUID,
    payload: OrganizationUpdateRequest,
) -> Organization:
    organization = _get_locked_organization(session, organization_id)
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=ORGANIZATION_MANAGE,
        organization_id=organization.id,
    )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return organization

    before = {
        "name": organization.name,
        "code": organization.code,
    }

    if "code" in changes:
        candidate_code = changes["code"]
        if candidate_code != organization.code and _code_exists(
            session,
            code=candidate_code,
            exclude_organization_id=organization.id,
        ):
            raise OrganizationConflictError("Organization code already exists.")
        organization.code = candidate_code
    if "name" in changes:
        organization.name = changes["name"]

    after = {
        "name": organization.name,
        "code": organization.code,
    }
    if before == after:
        return organization

    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action="organization.updated",
        resource_type="organization",
        resource_id=organization.id,
        before_state=before,
        after_state=after,
    )
    session.commit()
    session.refresh(organization)
    return organization


def change_organization_status(
    session: Session,
    *,
    actor: User,
    organization_id: UUID,
    payload: OrganizationStatusRequest,
) -> Organization:
    organization = _get_locked_organization(session, organization_id)
    is_root_holding = (
        organization.organization_type is OrganizationType.HOLDING
        and organization.parent_id is None
    )

    if organization.is_active:
        require_permission_for_organization(
            session,
            user_id=actor.id,
            permission_code=ORGANIZATION_MANAGE,
            organization_id=organization.id,
        )
        if is_root_holding:
            raise OrganizationValidationError(
                "Root holding status is bootstrap-only and cannot be changed through the API."
            )
    elif is_root_holding:
        raise AuthorizationError("Permission denied.")
    elif payload.is_active:
        if not has_permission_including_inactive_target(
            session,
            user_id=actor.id,
            permission_code=ORGANIZATION_MANAGE,
            organization_id=organization.id,
        ):
            raise AuthorizationError("Permission denied.")
    else:
        # Idempotent inactive -> inactive is allowed only if the actor would have
        # authority to reactivate it; this avoids using status as an existence oracle.
        if not has_permission_including_inactive_target(
            session,
            user_id=actor.id,
            permission_code=ORGANIZATION_MANAGE,
            organization_id=organization.id,
        ):
            raise AuthorizationError("Permission denied.")

    if organization.is_active is payload.is_active:
        return organization

    if payload.is_active:
        if organization.parent_id is not None:
            parent = session.get(Organization, organization.parent_id)
            if parent is None or not parent.is_active:
                raise OrganizationConflictError(
                    "Cannot activate an organization while its parent is inactive."
                )
    else:
        has_active_child = session.scalar(
            select(Organization.id)
            .where(
                Organization.parent_id == organization.id,
                Organization.is_active.is_(True),
            )
            .limit(1)
        )
        if has_active_child is not None:
            raise OrganizationConflictError(
                "Deactivate active child organizations before deactivating the parent."
            )

    before = {"is_active": organization.is_active}
    organization.is_active = payload.is_active

    record_audit_event(
        session,
        actor=actor,
        organization_id=organization.id,
        action="organization.status.changed",
        resource_type="organization",
        resource_id=organization.id,
        before_state=before,
        after_state={"is_active": organization.is_active},
    )
    session.commit()
    session.refresh(organization)
    return organization


def search_organizations_for_user(
    session: Session,
    *,
    user_id: UUID,
    query: str,
    limit: int = 8,
) -> list[Organization]:
    allowed_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=ORGANIZATION_READ,
    )
    if not allowed_ids:
        return []

    normalized = query.strip().lower()
    if not normalized:
        return []
    pattern = f"%{normalized}%"
    statement = (
        select(Organization)
        .where(
            Organization.id.in_(allowed_ids),
            or_(
                func.lower(Organization.name).like(pattern),
                func.lower(Organization.code).like(pattern),
            ),
        )
        .order_by(Organization.name, Organization.id)
        .limit(limit)
    )
    return list(session.scalars(statement).all())
