from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.documents.schemas import (
    DocumentCategoryCreateRequest,
    DocumentCategoryResponse,
    DocumentCategoryUpdateRequest,
)
from app.core.documents.service import (
    DocumentCategoryConflictError,
    DocumentCategoryNotFoundError,
    DocumentMetadataValidationError,
    create_document_category,
    deactivate_document_category,
    list_document_categories,
    restore_document_category,
    update_document_category,
)
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db

router = APIRouter(prefix="/document-categories", tags=["document-categories"])


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, DocumentCategoryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DocumentCategoryConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, DocumentMetadataValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[DocumentCategoryResponse])
def read_document_categories(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    organization_id: UUID | None = None,
    include_inactive: bool = False,
) -> list[DocumentCategoryResponse]:
    try:
        categories = list_document_categories(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except AuthorizationError as exc:
        raise _translate(exc) from exc
    return [DocumentCategoryResponse.model_validate(item) for item in categories]


@router.post("", response_model=DocumentCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_document_category_endpoint(
    payload: DocumentCategoryCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentCategoryResponse:
    try:
        category = create_document_category(
            session,
            actor=current_user,
            organization_id=payload.organization_id,
            code=payload.code,
            name=payload.name,
            description=payload.description,
            parent_id=payload.parent_id,
        )
    except (
        AuthorizationError,
        DocumentCategoryNotFoundError,
        DocumentCategoryConflictError,
        DocumentMetadataValidationError,
    ) as exc:
        raise _translate(exc) from exc
    return DocumentCategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=DocumentCategoryResponse)
def update_document_category_endpoint(
    category_id: UUID,
    payload: DocumentCategoryUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentCategoryResponse:
    try:
        category = update_document_category(
            session,
            actor=current_user,
            category_id=category_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except (
        AuthorizationError,
        DocumentCategoryNotFoundError,
        DocumentCategoryConflictError,
        DocumentMetadataValidationError,
    ) as exc:
        raise _translate(exc) from exc
    return DocumentCategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_document_category_endpoint(
    category_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        deactivate_document_category(
            session,
            actor=current_user,
            category_id=category_id,
        )
    except (
        AuthorizationError,
        DocumentCategoryNotFoundError,
        DocumentCategoryConflictError,
    ) as exc:
        raise _translate(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{category_id}/restore", response_model=DocumentCategoryResponse)
def restore_document_category_endpoint(
    category_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentCategoryResponse:
    try:
        category = restore_document_category(
            session,
            actor=current_user,
            category_id=category_id,
        )
    except (
        AuthorizationError,
        DocumentCategoryNotFoundError,
    ) as exc:
        raise _translate(exc) from exc
    return DocumentCategoryResponse.model_validate(category)
