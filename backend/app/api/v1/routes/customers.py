from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db
from app.modules.customers.schemas import (
    CRMOrganizationCapabilityResponse,
    CRMAssigneeOptionResponse,
    CommerceActivityProjection,
    CustomerAssignmentRequest,
    CustomerCRMCreateRequest,
    CustomerCRMResponse,
    CustomerCRMStatusRequest,
    CustomerCRMUpdateRequest,
    CustomerNoteCreateRequest,
    CustomerNoteResponse,
    CustomerNoteUpdateRequest,
    CustomerTagCreateRequest,
    CustomerTagResponse,
    CustomerUnassignRequest,
)
from app.modules.customers.service import (
    CRMConflictError,
    CRMIntegrationUnavailableError,
    CRMNotFoundError,
    CRMValidationError,
    assign_customer_owner,
    attach_tag,
    change_customer_status,
    create_customer,
    create_note,
    create_tag,
    customer_response_data,
    detach_tag,
    get_commerce_activity_for_user,
    get_customer_for_user,
    list_assignees_for_user,
    list_crm_organizations_for_user,
    list_customers_for_user,
    list_notes_for_user,
    list_tags_for_user,
    unassign_customer_owner,
    update_customer,
    update_note,
)


router = APIRouter(prefix="/crm", tags=["crm"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, CRMNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (CRMConflictError, IntegrityError)):
        detail = str(exc) if not isinstance(exc, IntegrityError) else "CRM write conflict."
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, CRMValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if isinstance(exc, CRMIntegrationUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Commerce integration is temporarily unavailable.",
        )
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


def _customer_response(item) -> CustomerCRMResponse:
    return CustomerCRMResponse.model_validate(customer_response_data(item))


@router.get("/organizations", response_model=list[CRMOrganizationCapabilityResponse])
def list_crm_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[CRMOrganizationCapabilityResponse]:
    return [
        CRMOrganizationCapabilityResponse.model_validate(item)
        for item in list_crm_organizations_for_user(session, user_id=current_user.id)
    ]


@router.get("/assignees", response_model=list[CRMAssigneeOptionResponse])
def list_crm_assignees(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[CRMAssigneeOptionResponse]:
    try:
        items = list_assignees_for_user(
            session, user_id=current_user.id, organization_id=organization_id
        )
    except (AuthorizationError, CRMNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [CRMAssigneeOptionResponse.model_validate(item) for item in items]


@router.get("/customers", response_model=list[CustomerCRMResponse])
def list_crm_customers(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CustomerCRMResponse]:
    try:
        items = list_customers_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
            search=search,
            limit=limit,
            offset=offset,
        )
    except (AuthorizationError, CRMNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [_customer_response(item) for item in items]


@router.get("/customers/{customer_id}", response_model=CustomerCRMResponse)
def get_crm_customer(
    customer_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        return _customer_response(
            get_customer_for_user(session, user_id=current_user.id, customer_id=customer_id)
        )
    except (AuthorizationError, CRMNotFoundError) as exc:
        raise _translate_error(exc) from exc


@router.post(
    "/customers",
    response_model=CustomerCRMResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_crm_customer(
    payload: CustomerCRMCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = create_customer(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        CRMIntegrationUnavailableError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.patch("/customers/{customer_id}", response_model=CustomerCRMResponse)
def patch_crm_customer(
    customer_id: UUID,
    payload: CustomerCRMUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = update_customer(session, actor=current_user, customer_id=customer_id, payload=payload)
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.post("/customers/{customer_id}/status", response_model=CustomerCRMResponse)
def set_crm_customer_status(
    customer_id: UUID,
    payload: CustomerCRMStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = change_customer_status(
            session, actor=current_user, customer_id=customer_id, payload=payload
        )
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.post("/customers/{customer_id}/assign", response_model=CustomerCRMResponse)
def assign_crm_customer(
    customer_id: UUID,
    payload: CustomerAssignmentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = assign_customer_owner(
            session, actor=current_user, customer_id=customer_id, payload=payload
        )
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.post("/customers/{customer_id}/unassign", response_model=CustomerCRMResponse)
def unassign_crm_customer(
    customer_id: UUID,
    payload: CustomerUnassignRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = unassign_customer_owner(
            session, actor=current_user, customer_id=customer_id, payload=payload
        )
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.get("/customer-tags", response_model=list[CustomerTagResponse])
def list_crm_tags(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[CustomerTagResponse]:
    try:
        items = list_tags_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except (AuthorizationError, CRMNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [CustomerTagResponse.model_validate(item) for item in items]


@router.post(
    "/customer-tags",
    response_model=CustomerTagResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_crm_tag(
    payload: CustomerTagCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerTagResponse:
    try:
        item = create_tag(session, actor=current_user, payload=payload)
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return CustomerTagResponse.model_validate(item)


@router.post("/customers/{customer_id}/tags/{tag_id}", response_model=CustomerCRMResponse)
def add_crm_customer_tag(
    customer_id: UUID,
    tag_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = attach_tag(session, actor=current_user, customer_id=customer_id, tag_id=tag_id)
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.delete("/customers/{customer_id}/tags/{tag_id}", response_model=CustomerCRMResponse)
def remove_crm_customer_tag(
    customer_id: UUID,
    tag_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerCRMResponse:
    try:
        item = detach_tag(session, actor=current_user, customer_id=customer_id, tag_id=tag_id)
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return _customer_response(item)


@router.get("/customers/{customer_id}/notes", response_model=list[CustomerNoteResponse])
def list_crm_customer_notes(
    customer_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[CustomerNoteResponse]:
    try:
        items = list_notes_for_user(session, user_id=current_user.id, customer_id=customer_id)
    except (AuthorizationError, CRMNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [CustomerNoteResponse.model_validate(item) for item in items]


@router.post(
    "/customers/{customer_id}/notes",
    response_model=CustomerNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_crm_customer_note(
    customer_id: UUID,
    payload: CustomerNoteCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerNoteResponse:
    try:
        item = create_note(session, actor=current_user, customer_id=customer_id, payload=payload)
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return CustomerNoteResponse.model_validate(item)


@router.patch(
    "/customers/{customer_id}/notes/{note_id}",
    response_model=CustomerNoteResponse,
)
def patch_crm_customer_note(
    customer_id: UUID,
    note_id: UUID,
    payload: CustomerNoteUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CustomerNoteResponse:
    try:
        item = update_note(
            session,
            actor=current_user,
            customer_id=customer_id,
            note_id=note_id,
            payload=payload,
        )
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMConflictError,
        CRMValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return CustomerNoteResponse.model_validate(item)


@router.get(
    "/customers/{customer_id}/commerce-activity",
    response_model=CommerceActivityProjection,
)
def get_crm_customer_commerce_activity(
    customer_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> CommerceActivityProjection:
    try:
        return get_commerce_activity_for_user(
            session, user_id=current_user.id, customer_id=customer_id
        )
    except (
        AuthorizationError,
        CRMNotFoundError,
        CRMIntegrationUnavailableError,
    ) as exc:
        raise _translate_error(exc) from exc
