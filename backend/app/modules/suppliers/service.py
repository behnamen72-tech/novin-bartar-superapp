from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.access.policy import (
    AuthorizationError,
    has_permission,
    require_permission_for_organization,
)
from app.core.access.service import authorized_organization_ids
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.organization.models import Organization
from app.modules.suppliers.models import (
    SupplierCommercialStatus,
    SupplierExternalReference,
    SupplierNote,
    SupplierProfile,
    SupplierProfileTag,
    SupplierRepresentative,
    SupplierTag,
)
from app.modules.suppliers.permissions import (
    SUPPLIER_ASSIGN,
    SUPPLIER_EXTERNAL_REFERENCE_MANAGE,
    SUPPLIER_EXTERNAL_REFERENCE_READ,
    SUPPLIER_MANAGE,
    SUPPLIER_NOTES_MANAGE,
    SUPPLIER_NOTES_READ,
    SUPPLIER_READ,
    SUPPLIER_REPRESENTATIVE_CONTACT_READ,
    SUPPLIER_REPRESENTATIVE_MANAGE,
    SUPPLIER_REPRESENTATIVE_READ,
    SUPPLIER_TAGS_ASSIGN,
    SUPPLIER_TAGS_CATALOG_MANAGE,
)
from app.modules.suppliers.schemas import (
    SupplierAssignmentRequest,
    SupplierCreateRequest,
    SupplierExternalReferenceCreateRequest,
    SupplierNoteCreateRequest,
    SupplierNoteUpdateRequest,
    SupplierRepresentativeCreateRequest,
    SupplierRepresentativeUpdateRequest,
    SupplierStatusRequest,
    SupplierTagCreateRequest,
    SupplierUnassignRequest,
    SupplierUpdateRequest,
    normalize_external_id,
)


class SupplierNotFoundError(LookupError):
    pass


class SupplierConflictError(ValueError):
    pass


class SupplierValidationError(ValueError):
    pass


def _active_organization(session: Session, organization_id: UUID) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise SupplierNotFoundError("Organization not found.")
    return organization


def _require_resource_permission(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    permission_code: str,
    not_found_message: str = "Supplier not found.",
) -> None:
    if not has_permission(
        session,
        user_id=user_id,
        permission_code=permission_code,
        organization_id=organization_id,
    ):
        raise SupplierNotFoundError(not_found_message)


def _supplier_statement(supplier_id: UUID, *, for_update: bool = False):
    statement = (
        select(SupplierProfile)
        .where(SupplierProfile.id == supplier_id)
        .options(
            selectinload(SupplierProfile.tag_links).selectinload(SupplierProfileTag.tag),
            selectinload(SupplierProfile.organization),
        )
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_supplier(
    session: Session, supplier_id: UUID, *, for_update: bool = False
) -> SupplierProfile:
    supplier = session.scalar(_supplier_statement(supplier_id, for_update=for_update))
    if supplier is None:
        raise SupplierNotFoundError("Supplier not found.")
    return supplier


def _serialize_tags(supplier: SupplierProfile) -> list[SupplierTag]:
    return sorted(
        (link.tag for link in supplier.tag_links if link.tag.is_active),
        key=lambda item: (item.name.casefold(), str(item.id)),
    )


def supplier_response_data(supplier: SupplierProfile) -> dict[str, object]:
    return {
        "id": supplier.id,
        "organization_id": supplier.organization_id,
        "supplier_kind": supplier.supplier_kind,
        "display_name": supplier.display_name,
        "commercial_status": supplier.commercial_status,
        "source": supplier.source,
        "assigned_owner_user_id": supplier.assigned_owner_user_id,
        "created_by_user_id": supplier.created_by_user_id,
        "is_active": supplier.is_active,
        "version": supplier.version,
        "tags": _serialize_tags(supplier),
    }


def _mask_phone(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def _mask_email(value: str | None) -> str | None:
    if value is None:
        return None
    local, separator, domain = value.partition("@")
    if not separator:
        return "***"
    visible = local[:1] if local else ""
    return f"{visible}***@{domain}"


def representative_response_data(
    representative: SupplierRepresentative,
    *,
    can_read_contact: bool,
) -> dict[str, object]:
    return {
        "id": representative.id,
        "supplier_id": representative.supplier_id,
        "display_name": representative.display_name,
        "job_title": representative.job_title,
        "phone": representative.phone if can_read_contact else _mask_phone(representative.phone),
        "email": representative.email if can_read_contact else _mask_email(representative.email),
        "contact_masked": not can_read_contact,
        "is_primary": representative.is_primary,
        "is_active": representative.is_active,
        "version": representative.version,
        "created_at": representative.created_at,
        "updated_at": representative.updated_at,
    }


def list_supplier_organizations_for_user(
    session: Session, *, user_id: UUID
) -> list[dict[str, object]]:
    permission_codes = (
        SUPPLIER_READ,
        SUPPLIER_MANAGE,
        SUPPLIER_REPRESENTATIVE_READ,
        SUPPLIER_REPRESENTATIVE_MANAGE,
        SUPPLIER_REPRESENTATIVE_CONTACT_READ,
        SUPPLIER_NOTES_READ,
        SUPPLIER_NOTES_MANAGE,
        SUPPLIER_ASSIGN,
        SUPPLIER_TAGS_CATALOG_MANAGE,
        SUPPLIER_TAGS_ASSIGN,
        SUPPLIER_EXTERNAL_REFERENCE_READ,
        SUPPLIER_EXTERNAL_REFERENCE_MANAGE,
    )
    allowed = {
        code: authorized_organization_ids(session, user_id=user_id, permission_code=code)
        for code in permission_codes
    }
    visible_ids: set[UUID] = set().union(*allowed.values())
    if not visible_ids:
        return []
    organizations = session.scalars(
        select(Organization)
        .where(Organization.id.in_(visible_ids), Organization.is_active.is_(True))
        .order_by(Organization.name, Organization.id)
    ).all()
    return [
        {
            "id": org.id,
            "name": org.name,
            "code": org.code,
            "organization_type": org.organization_type.value,
            "parent_id": org.parent_id,
            "is_active": org.is_active,
            "can_read": org.id in allowed[SUPPLIER_READ],
            "can_manage": org.id in allowed[SUPPLIER_MANAGE],
            "can_read_representatives": org.id in allowed[SUPPLIER_REPRESENTATIVE_READ],
            "can_manage_representatives": org.id in allowed[SUPPLIER_REPRESENTATIVE_MANAGE],
            "can_read_representative_contacts": org.id
            in allowed[SUPPLIER_REPRESENTATIVE_CONTACT_READ],
            "can_read_notes": org.id in allowed[SUPPLIER_NOTES_READ],
            "can_manage_notes": org.id in allowed[SUPPLIER_NOTES_MANAGE],
            "can_assign": org.id in allowed[SUPPLIER_ASSIGN],
            "can_manage_tag_catalog": org.id in allowed[SUPPLIER_TAGS_CATALOG_MANAGE],
            "can_assign_tags": org.id in allowed[SUPPLIER_TAGS_ASSIGN],
            "can_read_external_references": org.id in allowed[SUPPLIER_EXTERNAL_REFERENCE_READ],
            "can_manage_external_references": org.id in allowed[SUPPLIER_EXTERNAL_REFERENCE_MANAGE],
        }
        for org in organizations
    ]


def list_assignees_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
) -> list[dict[str, object]]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=SUPPLIER_ASSIGN,
        organization_id=organization_id,
    )
    _active_organization(session, organization_id)
    users = session.scalars(
        select(User)
        .where(User.is_active.is_(True))
        .options(selectinload(User.person))
        .order_by(User.email, User.id)
    ).all()
    result: list[dict[str, object]] = []
    for user in users:
        if not user.person.is_active:
            continue
        if not any(
            has_permission(
                session,
                user_id=user.id,
                permission_code=code,
                organization_id=organization_id,
            )
            for code in (SUPPLIER_READ, SUPPLIER_MANAGE)
        ):
            continue
        result.append(
            {
                "id": user.id,
                "email": user.email,
                "display_name": f"{user.person.first_name} {user.person.last_name}".strip(),
            }
        )
    return result


def list_suppliers_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[SupplierProfile]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=SUPPLIER_READ,
        organization_id=organization_id,
    )
    _active_organization(session, organization_id)
    statement = (
        select(SupplierProfile)
        .where(SupplierProfile.organization_id == organization_id)
        .options(selectinload(SupplierProfile.tag_links).selectinload(SupplierProfileTag.tag))
        .order_by(SupplierProfile.updated_at.desc(), SupplierProfile.id)
    )
    if not include_inactive:
        statement = statement.where(SupplierProfile.is_active.is_(True))
    if search:
        normalized = search.strip()
        statement = statement.where(SupplierProfile.display_name.ilike(f"%{normalized}%"))
    return list(session.scalars(statement.offset(offset).limit(limit)).unique().all())


def get_supplier_for_user(session: Session, *, user_id: UUID, supplier_id: UUID) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
    )
    return supplier


def search_suppliers_for_user(
    session: Session,
    *,
    user_id: UUID,
    query: str,
    limit: int,
) -> list[SupplierProfile]:
    allowed_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=SUPPLIER_READ,
    )
    if not allowed_ids:
        return []
    statement = (
        select(SupplierProfile)
        .where(
            SupplierProfile.organization_id.in_(allowed_ids),
            SupplierProfile.is_active.is_(True),
            SupplierProfile.display_name.ilike(f"%{query}%"),
        )
        .options(selectinload(SupplierProfile.organization))
        .order_by(SupplierProfile.display_name, SupplierProfile.id)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def create_supplier(
    session: Session, *, actor: User, payload: SupplierCreateRequest
) -> SupplierProfile:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=SUPPLIER_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    supplier = SupplierProfile(
        organization_id=payload.organization_id,
        supplier_kind=payload.supplier_kind,
        display_name=payload.display_name,
        commercial_status=payload.commercial_status,
        source=payload.source,
        created_by_user_id=actor.id,
        is_active=True,
        version=1,
    )
    session.add(supplier)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.created",
        resource_type="supplier_profile",
        resource_id=supplier.id,
        after_state={
            "supplier_kind": supplier.supplier_kind.value,
            "commercial_status": supplier.commercial_status.value,
            "source": supplier.source.value,
            "is_active": supplier.is_active,
            "version": supplier.version,
        },
    )
    session.commit()
    return _get_supplier(session, supplier.id)


def update_supplier(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierUpdateRequest,
) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_MANAGE,
    )
    if supplier.version != payload.expected_version:
        raise SupplierConflictError("Supplier was modified by another request.")
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not changes:
        return supplier
    if changes.get("commercial_status") is SupplierCommercialStatus.ARCHIVED and supplier.is_active:
        raise SupplierValidationError("Archive the supplier through the lifecycle endpoint.")
    before = {
        "supplier_kind": supplier.supplier_kind.value,
        "commercial_status": supplier.commercial_status.value,
        "source": supplier.source.value,
        "is_active": supplier.is_active,
        "version": supplier.version,
    }
    changed_fields = sorted(changes)
    for key, value in changes.items():
        setattr(supplier, key, value)
    supplier.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.updated",
        resource_type="supplier_profile",
        resource_id=supplier.id,
        before_state=before,
        after_state={
            "supplier_kind": supplier.supplier_kind.value,
            "commercial_status": supplier.commercial_status.value,
            "source": supplier.source.value,
            "is_active": supplier.is_active,
            "version": supplier.version,
        },
        metadata={"changed_fields": changed_fields},
    )
    session.commit()
    return _get_supplier(session, supplier.id)


def change_supplier_status(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierStatusRequest,
) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_MANAGE,
    )
    if supplier.version != payload.expected_version:
        raise SupplierConflictError("Supplier was modified by another request.")
    if supplier.is_active is payload.is_active:
        return supplier
    before = {
        "is_active": supplier.is_active,
        "commercial_status": supplier.commercial_status.value,
        "version": supplier.version,
    }
    supplier.is_active = payload.is_active
    if not payload.is_active:
        supplier.commercial_status = SupplierCommercialStatus.ARCHIVED
    elif supplier.commercial_status is SupplierCommercialStatus.ARCHIVED:
        supplier.commercial_status = SupplierCommercialStatus.INACTIVE
    supplier.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.status.changed",
        resource_type="supplier_profile",
        resource_id=supplier.id,
        before_state=before,
        after_state={
            "is_active": supplier.is_active,
            "commercial_status": supplier.commercial_status.value,
            "version": supplier.version,
        },
    )
    session.commit()
    return _get_supplier(session, supplier.id)


def _validate_assignee(session: Session, *, user_id: UUID, organization_id: UUID) -> User:
    user = session.get(User, user_id)
    if user is None or not user.is_active or not user.person.is_active:
        raise SupplierValidationError("Assigned owner is not an active internal user.")
    if not any(
        has_permission(
            session,
            user_id=user.id,
            permission_code=code,
            organization_id=organization_id,
        )
        for code in (SUPPLIER_READ, SUPPLIER_MANAGE)
    ):
        raise SupplierValidationError(
            "Assigned owner cannot access this organization supplier context."
        )
    return user


def assign_supplier_owner(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierAssignmentRequest,
) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_ASSIGN,
    )
    if supplier.version != payload.expected_version:
        raise SupplierConflictError("Supplier was modified by another request.")
    _validate_assignee(
        session, user_id=payload.assigned_owner_user_id, organization_id=supplier.organization_id
    )
    previous = supplier.assigned_owner_user_id
    supplier.assigned_owner_user_id = payload.assigned_owner_user_id
    supplier.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.assigned",
        resource_type="supplier_profile",
        resource_id=supplier.id,
        before_state={"assigned_owner_user_id": previous, "version": payload.expected_version},
        after_state={
            "assigned_owner_user_id": supplier.assigned_owner_user_id,
            "version": supplier.version,
        },
    )
    session.commit()
    return _get_supplier(session, supplier.id)


def unassign_supplier_owner(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierUnassignRequest,
) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_ASSIGN,
    )
    if supplier.version != payload.expected_version:
        raise SupplierConflictError("Supplier was modified by another request.")
    previous = supplier.assigned_owner_user_id
    supplier.assigned_owner_user_id = None
    supplier.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.unassigned",
        resource_type="supplier_profile",
        resource_id=supplier.id,
        before_state={"assigned_owner_user_id": previous, "version": payload.expected_version},
        after_state={"assigned_owner_user_id": None, "version": supplier.version},
    )
    session.commit()
    return _get_supplier(session, supplier.id)


def _representative_for_supplier(
    session: Session,
    *,
    supplier_id: UUID,
    representative_id: UUID,
    for_update: bool = False,
) -> SupplierRepresentative:
    statement = select(SupplierRepresentative).where(
        SupplierRepresentative.id == representative_id,
        SupplierRepresentative.supplier_id == supplier_id,
    )
    if for_update:
        statement = statement.with_for_update()
    representative = session.scalar(statement)
    if representative is None:
        raise SupplierNotFoundError("Supplier representative not found.")
    return representative


def list_representatives_for_user(
    session: Session,
    *,
    user_id: UUID,
    supplier_id: UUID,
    include_inactive: bool = False,
) -> tuple[list[SupplierRepresentative], bool]:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier representative not found.",
    )
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_REPRESENTATIVE_READ,
        not_found_message="Supplier representative not found.",
    )
    statement = select(SupplierRepresentative).where(
        SupplierRepresentative.supplier_id == supplier.id
    )
    if not include_inactive:
        statement = statement.where(SupplierRepresentative.is_active.is_(True))
    representatives = list(
        session.scalars(
            statement.order_by(
                SupplierRepresentative.is_primary.desc(),
                SupplierRepresentative.display_name,
                SupplierRepresentative.id,
            )
        ).all()
    )
    can_read_contact = has_permission(
        session,
        user_id=user_id,
        permission_code=SUPPLIER_REPRESENTATIVE_CONTACT_READ,
        organization_id=supplier.organization_id,
    )
    return representatives, can_read_contact


def create_representative(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierRepresentativeCreateRequest,
) -> SupplierRepresentative:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier representative not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_REPRESENTATIVE_MANAGE,
        not_found_message="Supplier representative not found.",
    )
    representative = SupplierRepresentative(
        supplier_id=supplier.id,
        display_name=payload.display_name,
        job_title=payload.job_title,
        phone=payload.phone,
        email=payload.email,
        is_primary=payload.is_primary,
        is_active=True,
        version=1,
    )
    session.add(representative)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SupplierConflictError(
            "Supplier already has an active primary representative."
        ) from exc
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.representative.created",
        resource_type="supplier_representative",
        resource_id=representative.id,
        after_state={
            "supplier_id": supplier.id,
            "is_primary": representative.is_primary,
            "is_active": True,
            "version": 1,
        },
    )
    session.commit()
    session.refresh(representative)
    return representative


def update_representative(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    representative_id: UUID,
    payload: SupplierRepresentativeUpdateRequest,
) -> SupplierRepresentative:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier representative not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_REPRESENTATIVE_MANAGE,
        not_found_message="Supplier representative not found.",
    )
    representative = _representative_for_supplier(
        session, supplier_id=supplier.id, representative_id=representative_id, for_update=True
    )
    if representative.version != payload.expected_version:
        raise SupplierConflictError("Supplier representative was modified by another request.")
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not changes:
        return representative
    previous_version = representative.version
    before = {
        "is_primary": representative.is_primary,
        "is_active": representative.is_active,
        "version": previous_version,
    }
    changed_fields = sorted(changes)
    for key, value in changes.items():
        setattr(representative, key, value)
    representative.version += 1
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SupplierConflictError(
            "Supplier already has an active primary representative."
        ) from exc
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.representative.updated",
        resource_type="supplier_representative",
        resource_id=representative.id,
        before_state=before,
        after_state={
            "is_primary": representative.is_primary,
            "is_active": representative.is_active,
            "version": representative.version,
        },
        metadata={"supplier_id": supplier.id, "changed_fields": changed_fields},
    )
    session.commit()
    session.refresh(representative)
    return representative


def list_tags_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
) -> list[SupplierTag]:
    if not any(
        has_permission(
            session, user_id=user_id, permission_code=code, organization_id=organization_id
        )
        for code in (SUPPLIER_READ, SUPPLIER_TAGS_CATALOG_MANAGE, SUPPLIER_TAGS_ASSIGN)
    ):
        raise AuthorizationError("Permission denied.")
    statement = select(SupplierTag).where(SupplierTag.organization_id == organization_id)
    if not include_inactive:
        statement = statement.where(SupplierTag.is_active.is_(True))
    return list(session.scalars(statement.order_by(SupplierTag.name, SupplierTag.id)).all())


def create_tag(session: Session, *, actor: User, payload: SupplierTagCreateRequest) -> SupplierTag:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=SUPPLIER_TAGS_CATALOG_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    tag = SupplierTag(
        organization_id=payload.organization_id,
        name=payload.name,
        normalized_name=payload.name.casefold(),
        is_active=True,
        created_by_user_id=actor.id,
    )
    session.add(tag)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SupplierConflictError("Supplier tag already exists in this organization.") from exc
    record_audit_event(
        session,
        actor=actor,
        organization_id=tag.organization_id,
        action="supplier.tag.created",
        resource_type="supplier_tag",
        resource_id=tag.id,
        after_state={"is_active": True},
    )
    session.commit()
    session.refresh(tag)
    return tag


def attach_tag(
    session: Session, *, actor: User, supplier_id: UUID, tag_id: UUID
) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_TAGS_ASSIGN,
    )
    tag = session.get(SupplierTag, tag_id)
    if tag is None or not tag.is_active or tag.organization_id != supplier.organization_id:
        raise SupplierNotFoundError("Supplier tag not found.")
    existing = session.get(SupplierProfileTag, (supplier.id, tag.id))
    if existing is None:
        session.add(
            SupplierProfileTag(supplier_id=supplier.id, tag_id=tag.id, created_by_user_id=actor.id)
        )
        supplier.version += 1
        record_audit_event(
            session,
            actor=actor,
            organization_id=supplier.organization_id,
            action="supplier.tag.added",
            resource_type="supplier_profile",
            resource_id=supplier.id,
            metadata={"tag_id": tag.id, "version": supplier.version},
        )
        session.commit()
    return _get_supplier(session, supplier.id)


def detach_tag(
    session: Session, *, actor: User, supplier_id: UUID, tag_id: UUID
) -> SupplierProfile:
    supplier = _get_supplier(session, supplier_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_TAGS_ASSIGN,
    )
    link = session.get(SupplierProfileTag, (supplier.id, tag_id))
    if link is not None:
        session.delete(link)
        supplier.version += 1
        record_audit_event(
            session,
            actor=actor,
            organization_id=supplier.organization_id,
            action="supplier.tag.removed",
            resource_type="supplier_profile",
            resource_id=supplier.id,
            metadata={"tag_id": tag_id, "version": supplier.version},
        )
        session.commit()
    return _get_supplier(session, supplier.id)


def list_notes_for_user(
    session: Session, *, user_id: UUID, supplier_id: UUID
) -> list[SupplierNote]:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier note not found.",
    )
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_NOTES_READ,
        not_found_message="Supplier note not found.",
    )
    return list(
        session.scalars(
            select(SupplierNote)
            .where(SupplierNote.supplier_id == supplier.id)
            .order_by(SupplierNote.created_at.desc(), SupplierNote.id)
        ).all()
    )


def create_note(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierNoteCreateRequest,
) -> SupplierNote:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier note not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_NOTES_MANAGE,
        not_found_message="Supplier note not found.",
    )
    note = SupplierNote(
        supplier_id=supplier.id, author_user_id=actor.id, body=payload.body, version=1
    )
    session.add(note)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.note.created",
        resource_type="supplier_note",
        resource_id=note.id,
        metadata={"supplier_id": supplier.id, "version": 1},
    )
    session.commit()
    session.refresh(note)
    return note


def update_note(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    note_id: UUID,
    payload: SupplierNoteUpdateRequest,
) -> SupplierNote:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier note not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_NOTES_MANAGE,
        not_found_message="Supplier note not found.",
    )
    note = session.scalar(
        select(SupplierNote)
        .where(SupplierNote.id == note_id, SupplierNote.supplier_id == supplier.id)
        .with_for_update()
    )
    if note is None:
        raise SupplierNotFoundError("Supplier note not found.")
    if note.version != payload.expected_version:
        raise SupplierConflictError("Supplier note was modified by another request.")
    previous_version = note.version
    note.body = payload.body
    note.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.note.updated",
        resource_type="supplier_note",
        resource_id=note.id,
        metadata={
            "supplier_id": supplier.id,
            "previous_version": previous_version,
            "new_version": note.version,
        },
    )
    session.commit()
    session.refresh(note)
    return note


def list_external_references_for_user(
    session: Session,
    *,
    user_id: UUID,
    supplier_id: UUID,
) -> list[SupplierExternalReference]:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier external reference not found.",
    )
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_EXTERNAL_REFERENCE_READ,
        not_found_message="Supplier external reference not found.",
    )
    return list(
        session.scalars(
            select(SupplierExternalReference)
            .where(SupplierExternalReference.supplier_id == supplier.id)
            .order_by(
                SupplierExternalReference.system,
                SupplierExternalReference.created_at,
                SupplierExternalReference.id,
            )
        ).all()
    )


def create_external_reference(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    payload: SupplierExternalReferenceCreateRequest,
) -> SupplierExternalReference:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier external reference not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_EXTERNAL_REFERENCE_MANAGE,
        not_found_message="Supplier external reference not found.",
    )
    normalized = normalize_external_id(payload.external_id)
    reference = SupplierExternalReference(
        supplier_id=supplier.id,
        organization_id=supplier.organization_id,
        system=payload.system,
        external_id=normalized,
        normalized_external_id=normalized,
        created_by_user_id=actor.id,
    )
    session.add(reference)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise SupplierConflictError(
            "External reference already exists in this organization and system."
        ) from exc
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.external_reference.created",
        resource_type="supplier_external_reference",
        resource_id=reference.id,
        metadata={"supplier_id": supplier.id, "system": reference.system.value},
    )
    session.commit()
    session.refresh(reference)
    return reference


def remove_external_reference(
    session: Session,
    *,
    actor: User,
    supplier_id: UUID,
    reference_id: UUID,
) -> None:
    supplier = _get_supplier(session, supplier_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_READ,
        not_found_message="Supplier external reference not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=supplier.organization_id,
        permission_code=SUPPLIER_EXTERNAL_REFERENCE_MANAGE,
        not_found_message="Supplier external reference not found.",
    )
    reference = session.scalar(
        select(SupplierExternalReference)
        .where(
            SupplierExternalReference.id == reference_id,
            SupplierExternalReference.supplier_id == supplier.id,
        )
        .with_for_update()
    )
    if reference is None:
        raise SupplierNotFoundError("Supplier external reference not found.")
    system = reference.system.value
    session.delete(reference)
    record_audit_event(
        session,
        actor=actor,
        organization_id=supplier.organization_id,
        action="supplier.external_reference.removed",
        resource_type="supplier_external_reference",
        resource_id=reference_id,
        metadata={"supplier_id": supplier.id, "system": system},
    )
    session.commit()
