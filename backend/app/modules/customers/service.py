from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, or_, select
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
from app.modules.customers.integration import (
    CommerceIntegrationProtocolError,
    CommerceIntegrationUnavailableError,
    fetch_commerce_customer_activity,
    validate_commerce_customer_reference,
)
from app.modules.customers.models import (
    CommercialStatus,
    CustomerCRMRecord,
    CustomerCRMTag,
    CustomerNote,
    CustomerTag,
)
from app.modules.customers.permissions import (
    CRM_CUSTOMER_ASSIGN,
    CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,
    CRM_CUSTOMER_MANAGE,
    CRM_CUSTOMER_NOTES_MANAGE,
    CRM_CUSTOMER_NOTES_READ,
    CRM_CUSTOMER_READ,
    CRM_CUSTOMER_TAGS_MANAGE,
)
from app.modules.customers.schemas import (
    CommerceActivityProjection,
    CustomerAssignmentRequest,
    CustomerCRMCreateRequest,
    CustomerCRMStatusRequest,
    CustomerCRMUpdateRequest,
    CustomerNoteCreateRequest,
    CustomerNoteUpdateRequest,
    CustomerTagCreateRequest,
    CustomerUnassignRequest,
)


class CRMNotFoundError(LookupError):
    pass


class CRMConflictError(ValueError):
    pass


class CRMValidationError(ValueError):
    pass


class CRMIntegrationUnavailableError(RuntimeError):
    pass


def _active_organization(session: Session, organization_id: UUID) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise CRMNotFoundError("Organization not found.")
    return organization


def _require_resource_permission(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    permission_code: str,
    not_found_message: str = "Customer not found.",
) -> None:
    # Resource-ID endpoints intentionally hide existence outside authorized scope.
    if not has_permission(
        session,
        user_id=user_id,
        permission_code=permission_code,
        organization_id=organization_id,
    ):
        raise CRMNotFoundError(not_found_message)


def _customer_statement(
    customer_id: UUID, *, for_update: bool = False
) -> Select[tuple[CustomerCRMRecord]]:
    statement = (
        select(CustomerCRMRecord)
        .where(CustomerCRMRecord.id == customer_id)
        .options(
            selectinload(CustomerCRMRecord.tag_links).selectinload(CustomerCRMTag.tag),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    return statement


def _get_customer(
    session: Session,
    customer_id: UUID,
    *,
    for_update: bool = False,
) -> CustomerCRMRecord:
    customer = session.scalar(_customer_statement(customer_id, for_update=for_update))
    if customer is None:
        raise CRMNotFoundError("Customer not found.")
    return customer


def _serialize_tags(customer: CustomerCRMRecord) -> list[CustomerTag]:
    return sorted(
        (link.tag for link in customer.tag_links if link.tag.is_active),
        key=lambda item: (item.name.casefold(), str(item.id)),
    )


def customer_response_data(customer: CustomerCRMRecord) -> dict[str, object]:
    return {
        "id": customer.id,
        "organization_id": customer.organization_id,
        "commerce_customer_ref": customer.commerce_customer_ref,
        "customer_type": customer.customer_type,
        "commercial_status": customer.commercial_status,
        "source": customer.source,
        "display_label": customer.display_label,
        "assigned_owner_user_id": customer.assigned_owner_user_id,
        "created_by_user_id": customer.created_by_user_id,
        "is_active": customer.is_active,
        "version": customer.version,
        "tags": _serialize_tags(customer),
    }


def list_crm_organizations_for_user(
    session: Session,
    *,
    user_id: UUID,
) -> list[dict[str, object]]:
    permission_codes = (
        CRM_CUSTOMER_READ,
        CRM_CUSTOMER_MANAGE,
        CRM_CUSTOMER_NOTES_READ,
        CRM_CUSTOMER_NOTES_MANAGE,
        CRM_CUSTOMER_ASSIGN,
        CRM_CUSTOMER_TAGS_MANAGE,
        CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,
    )
    allowed_by_permission = {
        code: authorized_organization_ids(session, user_id=user_id, permission_code=code)
        for code in permission_codes
    }
    visible_ids: set[UUID] = set().union(*allowed_by_permission.values())
    if not visible_ids:
        return []
    organizations = session.scalars(
        select(Organization)
        .where(Organization.id.in_(visible_ids), Organization.is_active.is_(True))
        .order_by(Organization.name, Organization.id)
    ).all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "code": item.code,
            "organization_type": item.organization_type.value,
            "parent_id": item.parent_id,
            "is_active": item.is_active,
            "can_read": item.id in allowed_by_permission[CRM_CUSTOMER_READ],
            "can_manage": item.id in allowed_by_permission[CRM_CUSTOMER_MANAGE],
            "can_read_notes": item.id in allowed_by_permission[CRM_CUSTOMER_NOTES_READ],
            "can_manage_notes": item.id in allowed_by_permission[CRM_CUSTOMER_NOTES_MANAGE],
            "can_assign": item.id in allowed_by_permission[CRM_CUSTOMER_ASSIGN],
            "can_manage_tags": item.id in allowed_by_permission[CRM_CUSTOMER_TAGS_MANAGE],
            "can_read_commerce_activity": item.id
            in allowed_by_permission[CRM_CUSTOMER_COMMERCE_ACTIVITY_READ],
        }
        for item in organizations
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
        permission_code=CRM_CUSTOMER_ASSIGN,
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
            for code in (CRM_CUSTOMER_READ, CRM_CUSTOMER_MANAGE)
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


def list_customers_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[CustomerCRMRecord]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=CRM_CUSTOMER_READ,
        organization_id=organization_id,
    )
    _active_organization(session, organization_id)
    statement = (
        select(CustomerCRMRecord)
        .where(CustomerCRMRecord.organization_id == organization_id)
        .options(selectinload(CustomerCRMRecord.tag_links).selectinload(CustomerCRMTag.tag))
        .order_by(CustomerCRMRecord.updated_at.desc(), CustomerCRMRecord.id)
    )
    if not include_inactive:
        statement = statement.where(CustomerCRMRecord.is_active.is_(True))
    if search:
        normalized = search.strip()
        statement = statement.where(
            or_(
                CustomerCRMRecord.display_label.ilike(f"%{normalized}%"),
                CustomerCRMRecord.commerce_customer_ref.ilike(f"%{normalized}%"),
            )
        )
    return list(session.scalars(statement.offset(offset).limit(limit)).unique().all())


def get_customer_for_user(
    session: Session,
    *,
    user_id: UUID,
    customer_id: UUID,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_READ,
    )
    return customer


def search_customers_for_user(
    session: Session,
    *,
    user_id: UUID,
    query: str,
    limit: int,
) -> list[CustomerCRMRecord]:
    allowed_ids = authorized_organization_ids(
        session,
        user_id=user_id,
        permission_code=CRM_CUSTOMER_READ,
    )
    if not allowed_ids:
        return []
    # Authorization scope is applied before LIMIT so search cannot become an ACL side channel.
    statement = (
        select(CustomerCRMRecord)
        .where(
            CustomerCRMRecord.organization_id.in_(allowed_ids),
            CustomerCRMRecord.is_active.is_(True),
            or_(
                CustomerCRMRecord.display_label.ilike(f"%{query}%"),
                CustomerCRMRecord.commerce_customer_ref.ilike(f"%{query}%"),
            ),
        )
        .options(selectinload(CustomerCRMRecord.organization))
        .order_by(CustomerCRMRecord.display_label, CustomerCRMRecord.id)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def create_customer(
    session: Session,
    *,
    actor: User,
    payload: CustomerCRMCreateRequest,
) -> CustomerCRMRecord:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=CRM_CUSTOMER_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    try:
        validation = validate_commerce_customer_reference(
            payload.commerce_customer_ref,
            organization_id=payload.organization_id,
        )
    except CommerceIntegrationUnavailableError as exc:
        raise CRMIntegrationUnavailableError(str(exc)) from exc
    except CommerceIntegrationProtocolError as exc:
        raise CRMIntegrationUnavailableError(str(exc)) from exc
    if not validation.exists:
        raise CRMValidationError("Commerce customer reference does not exist.")

    customer = CustomerCRMRecord(
        organization_id=payload.organization_id,
        commerce_customer_ref=payload.commerce_customer_ref,
        customer_type=payload.customer_type,
        commercial_status=payload.commercial_status,
        source=payload.source,
        display_label=payload.display_label,
        created_by_user_id=actor.id,
        is_active=True,
        version=1,
    )
    session.add(customer)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise CRMConflictError("CRM customer already exists for this organization.") from exc
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer.created",
        resource_type="customer_crm_record",
        resource_id=customer.id,
        after_state={
            "commerce_customer_ref": customer.commerce_customer_ref,
            "customer_type": customer.customer_type.value,
            "commercial_status": customer.commercial_status.value,
            "source": customer.source.value,
            "is_active": customer.is_active,
            "version": customer.version,
        },
    )
    session.commit()
    return _get_customer(session, customer.id)


def update_customer(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    payload: CustomerCRMUpdateRequest,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_MANAGE,
    )
    if customer.version != payload.expected_version:
        raise CRMConflictError("Customer record was modified by another request.")
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    if not changes:
        return customer
    before = {
        "customer_type": customer.customer_type.value,
        "commercial_status": customer.commercial_status.value,
        "source": customer.source.value,
        "is_active": customer.is_active,
        "version": customer.version,
    }
    if changes.get("commercial_status") is CommercialStatus.ARCHIVED and customer.is_active:
        raise CRMValidationError("Archive the CRM record through the lifecycle endpoint.")
    changed_fields = sorted(changes)
    for key, value in changes.items():
        setattr(customer, key, value)
    customer.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer.updated",
        resource_type="customer_crm_record",
        resource_id=customer.id,
        before_state=before,
        after_state={
            "customer_type": customer.customer_type.value,
            "commercial_status": customer.commercial_status.value,
            "source": customer.source.value,
            "is_active": customer.is_active,
            "version": customer.version,
        },
        metadata={"changed_fields": changed_fields},
    )
    session.commit()
    return _get_customer(session, customer.id)


def change_customer_status(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    payload: CustomerCRMStatusRequest,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_MANAGE,
    )
    if customer.version != payload.expected_version:
        raise CRMConflictError("Customer record was modified by another request.")
    if customer.is_active is payload.is_active:
        return customer
    before = {"is_active": customer.is_active, "version": customer.version}
    customer.is_active = payload.is_active
    if not payload.is_active:
        customer.commercial_status = CommercialStatus.ARCHIVED
    elif customer.commercial_status is CommercialStatus.ARCHIVED:
        customer.commercial_status = CommercialStatus.INACTIVE
    customer.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer.status.changed",
        resource_type="customer_crm_record",
        resource_id=customer.id,
        before_state=before,
        after_state={"is_active": customer.is_active, "version": customer.version},
    )
    session.commit()
    return _get_customer(session, customer.id)


def _validate_assignee(session: Session, *, user_id: UUID, organization_id: UUID) -> User:
    user = session.get(User, user_id)
    if user is None or not user.is_active or not user.person.is_active:
        raise CRMValidationError("Assigned owner is not an active internal user.")
    if not any(
        has_permission(
            session,
            user_id=user.id,
            permission_code=code,
            organization_id=organization_id,
        )
        for code in (CRM_CUSTOMER_READ, CRM_CUSTOMER_MANAGE)
    ):
        raise CRMValidationError("Assigned owner cannot access this organization CRM context.")
    return user


def assign_customer_owner(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    payload: CustomerAssignmentRequest,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_ASSIGN,
    )
    if customer.version != payload.expected_version:
        raise CRMConflictError("Customer record was modified by another request.")
    _validate_assignee(
        session,
        user_id=payload.assigned_owner_user_id,
        organization_id=customer.organization_id,
    )
    before_owner = customer.assigned_owner_user_id
    customer.assigned_owner_user_id = payload.assigned_owner_user_id
    customer.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer.assigned",
        resource_type="customer_crm_record",
        resource_id=customer.id,
        before_state={"assigned_owner_user_id": before_owner, "version": payload.expected_version},
        after_state={
            "assigned_owner_user_id": customer.assigned_owner_user_id,
            "version": customer.version,
        },
    )
    session.commit()
    return _get_customer(session, customer.id)


def unassign_customer_owner(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    payload: CustomerUnassignRequest,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_ASSIGN,
    )
    if customer.version != payload.expected_version:
        raise CRMConflictError("Customer record was modified by another request.")
    before_owner = customer.assigned_owner_user_id
    customer.assigned_owner_user_id = None
    customer.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer.unassigned",
        resource_type="customer_crm_record",
        resource_id=customer.id,
        before_state={"assigned_owner_user_id": before_owner, "version": payload.expected_version},
        after_state={"assigned_owner_user_id": None, "version": customer.version},
    )
    session.commit()
    return _get_customer(session, customer.id)


def list_tags_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_inactive: bool = False,
) -> list[CustomerTag]:
    # Tag vocabulary can be viewed by CRM readers or dedicated tag managers.
    if not (
        has_permission(
            session,
            user_id=user_id,
            permission_code=CRM_CUSTOMER_READ,
            organization_id=organization_id,
        )
        or has_permission(
            session,
            user_id=user_id,
            permission_code=CRM_CUSTOMER_TAGS_MANAGE,
            organization_id=organization_id,
        )
    ):
        raise AuthorizationError("Permission denied.")
    statement = select(CustomerTag).where(CustomerTag.organization_id == organization_id)
    if not include_inactive:
        statement = statement.where(CustomerTag.is_active.is_(True))
    return list(session.scalars(statement.order_by(CustomerTag.name, CustomerTag.id)).all())


def create_tag(
    session: Session,
    *,
    actor: User,
    payload: CustomerTagCreateRequest,
) -> CustomerTag:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=CRM_CUSTOMER_TAGS_MANAGE,
        organization_id=payload.organization_id,
    )
    _active_organization(session, payload.organization_id)
    tag = CustomerTag(
        organization_id=payload.organization_id,
        name=payload.name,
        normalized_name=payload.name.casefold(),
        created_by_user_id=actor.id,
        is_active=True,
    )
    session.add(tag)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise CRMConflictError("Customer tag already exists in this organization.") from exc
    record_audit_event(
        session,
        actor=actor,
        organization_id=tag.organization_id,
        action="crm.customer_tag.created",
        resource_type="customer_tag",
        resource_id=tag.id,
        after_state={"is_active": tag.is_active},
    )
    session.commit()
    session.refresh(tag)
    return tag


def attach_tag(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    tag_id: UUID,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_TAGS_MANAGE,
    )
    tag = session.get(CustomerTag, tag_id)
    if tag is None or not tag.is_active or tag.organization_id != customer.organization_id:
        raise CRMNotFoundError("Customer tag not found.")
    existing = session.get(CustomerCRMTag, (customer.id, tag.id))
    if existing is None:
        session.add(
            CustomerCRMTag(
                customer_crm_record_id=customer.id,
                tag_id=tag.id,
                created_by_user_id=actor.id,
            )
        )
        customer.version += 1
        record_audit_event(
            session,
            actor=actor,
            organization_id=customer.organization_id,
            action="crm.customer.tag.added",
            resource_type="customer_crm_record",
            resource_id=customer.id,
            metadata={"tag_id": tag.id, "version": customer.version},
        )
        session.commit()
    return _get_customer(session, customer.id)


def detach_tag(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    tag_id: UUID,
) -> CustomerCRMRecord:
    customer = _get_customer(session, customer_id, for_update=True)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_TAGS_MANAGE,
    )
    link = session.get(CustomerCRMTag, (customer.id, tag_id))
    if link is not None:
        session.delete(link)
        customer.version += 1
        record_audit_event(
            session,
            actor=actor,
            organization_id=customer.organization_id,
            action="crm.customer.tag.removed",
            resource_type="customer_crm_record",
            resource_id=customer.id,
            metadata={"tag_id": tag_id, "version": customer.version},
        )
        session.commit()
    return _get_customer(session, customer.id)


def list_notes_for_user(
    session: Session,
    *,
    user_id: UUID,
    customer_id: UUID,
) -> list[CustomerNote]:
    customer = _get_customer(session, customer_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_READ,
    )
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_NOTES_READ,
    )
    return list(
        session.scalars(
            select(CustomerNote)
            .where(CustomerNote.customer_crm_record_id == customer.id)
            .order_by(CustomerNote.created_at.desc(), CustomerNote.id)
        ).all()
    )


def create_note(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    payload: CustomerNoteCreateRequest,
) -> CustomerNote:
    customer = _get_customer(session, customer_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_READ,
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_NOTES_MANAGE,
    )
    note = CustomerNote(
        customer_crm_record_id=customer.id,
        author_user_id=actor.id,
        body=payload.body,
        version=1,
    )
    session.add(note)
    session.flush()
    # Security invariant: note.body is intentionally absent from all Audit payloads.
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer_note.created",
        resource_type="customer_note",
        resource_id=note.id,
        metadata={"customer_crm_record_id": customer.id, "version": note.version},
    )
    session.commit()
    session.refresh(note)
    return note


def update_note(
    session: Session,
    *,
    actor: User,
    customer_id: UUID,
    note_id: UUID,
    payload: CustomerNoteUpdateRequest,
) -> CustomerNote:
    note = session.scalar(select(CustomerNote).where(CustomerNote.id == note_id).with_for_update())
    if note is None or note.customer_crm_record_id != customer_id:
        raise CRMNotFoundError("Customer note not found.")
    customer = _get_customer(session, customer_id)
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_READ,
        not_found_message="Customer note not found.",
    )
    _require_resource_permission(
        session,
        user_id=actor.id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_NOTES_MANAGE,
        not_found_message="Customer note not found.",
    )
    if note.version != payload.expected_version:
        raise CRMConflictError("Customer note was modified by another request.")
    previous_version = note.version
    note.body = payload.body
    note.version += 1
    record_audit_event(
        session,
        actor=actor,
        organization_id=customer.organization_id,
        action="crm.customer_note.updated",
        resource_type="customer_note",
        resource_id=note.id,
        metadata={
            "customer_crm_record_id": customer.id,
            "previous_version": previous_version,
            "new_version": note.version,
        },
    )
    session.commit()
    session.refresh(note)
    return note


def get_commerce_activity_for_user(
    session: Session,
    *,
    user_id: UUID,
    customer_id: UUID,
) -> CommerceActivityProjection:
    customer = _get_customer(session, customer_id)
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_READ,
    )
    _require_resource_permission(
        session,
        user_id=user_id,
        organization_id=customer.organization_id,
        permission_code=CRM_CUSTOMER_COMMERCE_ACTIVITY_READ,
    )
    try:
        return fetch_commerce_customer_activity(
            customer.commerce_customer_ref,
            organization_id=customer.organization_id,
        )
    except (CommerceIntegrationUnavailableError, CommerceIntegrationProtocolError) as exc:
        raise CRMIntegrationUnavailableError(str(exc)) from exc
