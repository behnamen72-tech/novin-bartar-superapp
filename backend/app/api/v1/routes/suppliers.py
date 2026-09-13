from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError, has_permission
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db
from app.modules.suppliers.models import SupplierProfile, SupplierRepresentative
from app.modules.suppliers.permissions import SUPPLIER_REPRESENTATIVE_CONTACT_READ
from app.modules.suppliers.schemas import (
    SupplierAssigneeOptionResponse,
    SupplierAssignmentRequest,
    SupplierCreateRequest,
    SupplierExternalReferenceCreateRequest,
    SupplierExternalReferenceResponse,
    SupplierNoteCreateRequest,
    SupplierNoteResponse,
    SupplierNoteUpdateRequest,
    SupplierOrganizationCapabilityResponse,
    SupplierRepresentativeCreateRequest,
    SupplierRepresentativeResponse,
    SupplierRepresentativeUpdateRequest,
    SupplierResponse,
    SupplierStatusRequest,
    SupplierTagCreateRequest,
    SupplierTagResponse,
    SupplierUnassignRequest,
    SupplierUpdateRequest,
)
from app.modules.suppliers.service import (
    SupplierConflictError,
    SupplierNotFoundError,
    SupplierValidationError,
    assign_supplier_owner,
    attach_tag,
    change_supplier_status,
    create_external_reference,
    create_note,
    create_representative,
    create_supplier,
    create_tag,
    detach_tag,
    get_supplier_for_user,
    list_assignees_for_user,
    list_external_references_for_user,
    list_notes_for_user,
    list_representatives_for_user,
    list_supplier_organizations_for_user,
    list_suppliers_for_user,
    list_tags_for_user,
    remove_external_reference,
    representative_response_data,
    supplier_response_data,
    unassign_supplier_owner,
    update_note,
    update_representative,
    update_supplier,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, SupplierNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (SupplierConflictError, IntegrityError)):
        detail = str(exc) if not isinstance(exc, IntegrityError) else "Supplier write conflict."
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, SupplierValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


def _supplier_response(item: SupplierProfile) -> SupplierResponse:
    return SupplierResponse.model_validate(supplier_response_data(item))


def _representative_response(
    session: Session,
    *,
    actor_id: UUID,
    representative: SupplierRepresentative,
) -> SupplierRepresentativeResponse:
    supplier = get_supplier_for_user(
        session, user_id=actor_id, supplier_id=representative.supplier_id
    )
    can_read_contact = has_permission(
        session,
        user_id=actor_id,
        permission_code=SUPPLIER_REPRESENTATIVE_CONTACT_READ,
        organization_id=supplier.organization_id,
    )
    return SupplierRepresentativeResponse.model_validate(
        representative_response_data(representative, can_read_contact=can_read_contact)
    )


@router.get("/organizations", response_model=list[SupplierOrganizationCapabilityResponse])
def list_supplier_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SupplierOrganizationCapabilityResponse]:
    return [
        SupplierOrganizationCapabilityResponse.model_validate(item)
        for item in list_supplier_organizations_for_user(session, user_id=current_user.id)
    ]


@router.get("/assignees", response_model=list[SupplierAssigneeOptionResponse])
def list_supplier_assignees(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SupplierAssigneeOptionResponse]:
    try:
        items = list_assignees_for_user(
            session, user_id=current_user.id, organization_id=organization_id
        )
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [SupplierAssigneeOptionResponse.model_validate(item) for item in items]


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SupplierResponse]:
    try:
        items = list_suppliers_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
            search=search,
            limit=limit,
            offset=offset,
        )
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [_supplier_response(item) for item in items]


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_endpoint(
    payload: SupplierCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(create_supplier(session, actor=current_user, payload=payload))
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier_endpoint(
    supplier_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            get_supplier_for_user(session, user_id=current_user.id, supplier_id=supplier_id)
        )
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc


@router.patch("/{supplier_id}", response_model=SupplierResponse)
def update_supplier_endpoint(
    supplier_id: UUID,
    payload: SupplierUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            update_supplier(session, actor=current_user, supplier_id=supplier_id, payload=payload)
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.post("/{supplier_id}/status", response_model=SupplierResponse)
def change_supplier_status_endpoint(
    supplier_id: UUID,
    payload: SupplierStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            change_supplier_status(
                session, actor=current_user, supplier_id=supplier_id, payload=payload
            )
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.post("/{supplier_id}/assign", response_model=SupplierResponse)
def assign_supplier_endpoint(
    supplier_id: UUID,
    payload: SupplierAssignmentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            assign_supplier_owner(
                session, actor=current_user, supplier_id=supplier_id, payload=payload
            )
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.post("/{supplier_id}/unassign", response_model=SupplierResponse)
def unassign_supplier_endpoint(
    supplier_id: UUID,
    payload: SupplierUnassignRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            unassign_supplier_owner(
                session, actor=current_user, supplier_id=supplier_id, payload=payload
            )
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.get("/{supplier_id}/representatives", response_model=list[SupplierRepresentativeResponse])
def list_representatives_endpoint(
    supplier_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[SupplierRepresentativeResponse]:
    try:
        representatives, can_read_contact = list_representatives_for_user(
            session,
            user_id=current_user.id,
            supplier_id=supplier_id,
            include_inactive=include_inactive,
        )
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [
        SupplierRepresentativeResponse.model_validate(
            representative_response_data(item, can_read_contact=can_read_contact)
        )
        for item in representatives
    ]


@router.post(
    "/{supplier_id}/representatives",
    response_model=SupplierRepresentativeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_representative_endpoint(
    supplier_id: UUID,
    payload: SupplierRepresentativeCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierRepresentativeResponse:
    try:
        representative = create_representative(
            session, actor=current_user, supplier_id=supplier_id, payload=payload
        )
        return _representative_response(
            session, actor_id=current_user.id, representative=representative
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch(
    "/{supplier_id}/representatives/{representative_id}",
    response_model=SupplierRepresentativeResponse,
)
def update_representative_endpoint(
    supplier_id: UUID,
    representative_id: UUID,
    payload: SupplierRepresentativeUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierRepresentativeResponse:
    try:
        representative = update_representative(
            session,
            actor=current_user,
            supplier_id=supplier_id,
            representative_id=representative_id,
            payload=payload,
        )
        return _representative_response(
            session, actor_id=current_user.id, representative=representative
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.get("/tags/catalog", response_model=list[SupplierTagResponse])
def list_supplier_tags_endpoint(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_inactive: bool = Query(default=False),
) -> list[SupplierTagResponse]:
    try:
        items = list_tags_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [SupplierTagResponse.model_validate(item) for item in items]


@router.post(
    "/tags/catalog", response_model=SupplierTagResponse, status_code=status.HTTP_201_CREATED
)
def create_supplier_tag_endpoint(
    payload: SupplierTagCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierTagResponse:
    try:
        return SupplierTagResponse.model_validate(
            create_tag(session, actor=current_user, payload=payload)
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.post("/{supplier_id}/tags/{tag_id}", response_model=SupplierResponse)
def attach_supplier_tag_endpoint(
    supplier_id: UUID,
    tag_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            attach_tag(session, actor=current_user, supplier_id=supplier_id, tag_id=tag_id)
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.delete("/{supplier_id}/tags/{tag_id}", response_model=SupplierResponse)
def detach_supplier_tag_endpoint(
    supplier_id: UUID,
    tag_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierResponse:
    try:
        return _supplier_response(
            detach_tag(session, actor=current_user, supplier_id=supplier_id, tag_id=tag_id)
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.get("/{supplier_id}/notes", response_model=list[SupplierNoteResponse])
def list_notes_endpoint(
    supplier_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SupplierNoteResponse]:
    try:
        items = list_notes_for_user(session, user_id=current_user.id, supplier_id=supplier_id)
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [SupplierNoteResponse.model_validate(item) for item in items]


@router.post(
    "/{supplier_id}/notes", response_model=SupplierNoteResponse, status_code=status.HTTP_201_CREATED
)
def create_note_endpoint(
    supplier_id: UUID,
    payload: SupplierNoteCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierNoteResponse:
    try:
        return SupplierNoteResponse.model_validate(
            create_note(session, actor=current_user, supplier_id=supplier_id, payload=payload)
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.patch("/{supplier_id}/notes/{note_id}", response_model=SupplierNoteResponse)
def update_note_endpoint(
    supplier_id: UUID,
    note_id: UUID,
    payload: SupplierNoteUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierNoteResponse:
    try:
        return SupplierNoteResponse.model_validate(
            update_note(
                session,
                actor=current_user,
                supplier_id=supplier_id,
                note_id=note_id,
                payload=payload,
            )
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.get(
    "/{supplier_id}/external-references", response_model=list[SupplierExternalReferenceResponse]
)
def list_external_references_endpoint(
    supplier_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[SupplierExternalReferenceResponse]:
    try:
        items = list_external_references_for_user(
            session, user_id=current_user.id, supplier_id=supplier_id
        )
    except (AuthorizationError, SupplierNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return [SupplierExternalReferenceResponse.model_validate(item) for item in items]


@router.post(
    "/{supplier_id}/external-references",
    response_model=SupplierExternalReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_external_reference_endpoint(
    supplier_id: UUID,
    payload: SupplierExternalReferenceCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> SupplierExternalReferenceResponse:
    try:
        return SupplierExternalReferenceResponse.model_validate(
            create_external_reference(
                session, actor=current_user, supplier_id=supplier_id, payload=payload
            )
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc


@router.delete(
    "/{supplier_id}/external-references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_external_reference_endpoint(
    supplier_id: UUID,
    reference_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        remove_external_reference(
            session,
            actor=current_user,
            supplier_id=supplier_id,
            reference_id=reference_id,
        )
    except (
        AuthorizationError,
        SupplierNotFoundError,
        SupplierConflictError,
        SupplierValidationError,
        IntegrityError,
        ValueError,
    ) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
