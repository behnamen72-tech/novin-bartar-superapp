from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.config import settings
from app.core.documents.dependencies import get_document_storage
from app.core.documents.models import (
    Document,
    DocumentLinkEntityType,
    DocumentPriority,
    DocumentStatus,
)
from app.core.documents.schemas import (
    DocumentCreateRequest,
    DocumentDetailResponse,
    DocumentExpirationResponse,
    DocumentExpirationState,
    DocumentLinkCreateRequest,
    DocumentLinkResponse,
    DocumentMetadataUpdateRequest,
    DocumentPermissionCreateRequest,
    DocumentPermissionResponse,
    DocumentResponse,
    DocumentRetentionDueResponse,
    DocumentTimelineEventResponse,
    DocumentVersionResponse,
)
from app.core.documents.security import DocumentUploadValidationError
from app.core.documents.service import (
    DocumentCategoryNotFoundError,
    DocumentLinkConflictError,
    DocumentLinkFilterError,
    DocumentLinkNotFoundError,
    DocumentLinkTargetNotFoundError,
    DocumentMetadataValidationError,
    DocumentNotFoundError,
    DocumentPermissionConflictError,
    DocumentPermissionNotFoundError,
    DocumentPermissionTargetNotFoundError,
    DocumentStateConflictError,
    RetentionPolicyNotFoundError,
    add_document_link,
    archive_document,
    create_document,
    create_document_version,
    download_latest_document,
    get_document_for_user,
    grant_document_permission,
    list_document_links,
    list_document_permissions,
    list_document_timeline,
    list_documents,
    list_expiring_documents,
    list_retention_due_documents,
    restore_document,
    revoke_document_permission,
    unlink_document,
    update_document_metadata,
    version_to_response_data,
)
from app.core.documents.storage.interface import StorageProvider
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db

router = APIRouter(prefix="/documents", tags=["documents"])


def _translate_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )
    if isinstance(
        exc,
        (
            DocumentNotFoundError,
            DocumentLinkNotFoundError,
            DocumentLinkTargetNotFoundError,
            DocumentPermissionNotFoundError,
            DocumentPermissionTargetNotFoundError,
            DocumentCategoryNotFoundError,
            RetentionPolicyNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(
        exc,
        (
            DocumentStateConflictError,
            DocumentLinkConflictError,
            DocumentPermissionConflictError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    if isinstance(
        exc,
        (
            DocumentUploadValidationError,
            DocumentLinkFilterError,
            DocumentMetadataValidationError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    raise exc


def _document_detail_response(document: Document) -> DocumentDetailResponse:
    return DocumentDetailResponse(
        **DocumentResponse.model_validate(document).model_dump(),
        versions=[
            DocumentVersionResponse.model_validate(version_to_response_data(version))
            for version in document.versions
        ],
        links=[
            DocumentLinkResponse.model_validate(link) for link in document.links if link.is_active
        ],
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _calendar_days_between(later: datetime, earlier: datetime) -> int:
    return (_aware_utc(later).date() - _aware_utc(earlier).date()).days


@router.get("", response_model=list[DocumentResponse])
def read_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    organization_id: UUID | None = None,
    document_type: str | None = Query(default=None, max_length=100),
    document_status: DocumentStatus | None = Query(default=None, alias="status"),
    entity_type: DocumentLinkEntityType | None = Query(default=None),
    entity_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=200),
    category_id: UUID | None = None,
    priority: DocumentPriority | None = None,
    expires_before: datetime | None = None,
    expires_after: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentResponse]:
    try:
        documents = list_documents(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            document_type=document_type,
            status=document_status,
            entity_type=entity_type,
            entity_id=entity_id,
            search=q,
            category_id=category_id,
            priority=priority,
            expires_before=expires_before,
            expires_after=expires_after,
            limit=limit,
            offset=offset,
        )
    except (AuthorizationError, DocumentLinkFilterError) as exc:
        raise _translate_service_error(exc) from exc

    return [DocumentResponse.model_validate(document) for document in documents]


# Static paths must be registered before /{document_id}.
@router.get("/expiring", response_model=list[DocumentExpirationResponse])
def read_expiring_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    organization_id: UUID | None = None,
    within_days: Annotated[int, Query(ge=0, le=3650)] = 30,
    include_expired: bool = True,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentExpirationResponse]:
    current = datetime.now(UTC)
    try:
        documents = list_expiring_documents(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            within_days=within_days,
            include_expired=include_expired,
            limit=limit,
            offset=offset,
            now=current,
        )
    except AuthorizationError as exc:
        raise _translate_service_error(exc) from exc

    result: list[DocumentExpirationResponse] = []
    for document in documents:
        assert document.expires_at is not None
        days_remaining = _calendar_days_between(document.expires_at, current)
        expiration_state = (
            DocumentExpirationState.EXPIRED
            if _aware_utc(document.expires_at) < current
            else DocumentExpirationState.EXPIRING_SOON
        )
        result.append(
            DocumentExpirationResponse(
                document=DocumentResponse.model_validate(document),
                expiration_state=expiration_state,
                days_remaining=days_remaining,
            )
        )
    return result


@router.get("/retention-due", response_model=list[DocumentRetentionDueResponse])
def read_retention_due_documents(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    organization_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentRetentionDueResponse]:
    current = datetime.now(UTC)
    try:
        documents = list_retention_due_documents(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            now=current,
        )
    except AuthorizationError as exc:
        raise _translate_service_error(exc) from exc

    return [
        DocumentRetentionDueResponse(
            document=DocumentResponse.model_validate(document),
            days_overdue=max(
                0,
                _calendar_days_between(current, document.retention_review_at),
            ),
        )
        for document in documents
        if document.retention_review_at is not None
    ]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document_endpoint(
    payload: DocumentCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    try:
        document = create_document(
            session,
            actor=current_user,
            title=payload.title,
            document_type=payload.document_type,
            organization_id=payload.organization_id,
        )
    except AuthorizationError as exc:
        raise _translate_service_error(exc) from exc

    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def read_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentDetailResponse:
    try:
        document = get_document_for_user(
            session,
            user_id=current_user.id,
            document_id=document_id,
        )
    except (AuthorizationError, DocumentNotFoundError) as exc:
        raise _translate_service_error(exc) from exc

    return _document_detail_response(document)


@router.patch("/{document_id}/metadata", response_model=DocumentResponse)
def update_document_metadata_endpoint(
    document_id: UUID,
    payload: DocumentMetadataUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    try:
        document = update_document_metadata(
            session,
            actor=current_user,
            document_id=document_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except (
        AuthorizationError,
        DocumentNotFoundError,
        DocumentStateConflictError,
        DocumentMetadataValidationError,
        DocumentCategoryNotFoundError,
        RetentionPolicyNotFoundError,
    ) as exc:
        raise _translate_service_error(exc) from exc
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/timeline", response_model=list[DocumentTimelineEventResponse])
def read_document_timeline(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentTimelineEventResponse]:
    try:
        events = list_document_timeline(
            session,
            user_id=current_user.id,
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
    except (AuthorizationError, DocumentNotFoundError) as exc:
        raise _translate_service_error(exc) from exc
    return [
        DocumentTimelineEventResponse(
            id=event.id,
            action=event.action,
            actor_identifier=event.actor_identifier,
            occurred_at=event.occurred_at,
            before_state=event.before_state,
            after_state=event.after_state,
            event_metadata=event.event_metadata,
        )
        for event in events
    ]


@router.post("/{document_id}/archive", response_model=DocumentResponse)
def archive_document_endpoint(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    try:
        document = archive_document(
            session,
            actor=current_user,
            document_id=document_id,
        )
    except (AuthorizationError, DocumentNotFoundError, DocumentStateConflictError) as exc:
        raise _translate_service_error(exc) from exc
    return DocumentResponse.model_validate(document)


@router.post("/{document_id}/restore", response_model=DocumentResponse)
def restore_document_endpoint(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentResponse:
    try:
        document = restore_document(
            session,
            actor=current_user,
            document_id=document_id,
        )
    except (AuthorizationError, DocumentNotFoundError, DocumentStateConflictError) as exc:
        raise _translate_service_error(exc) from exc
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/links", response_model=list[DocumentLinkResponse])
def read_document_links(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[DocumentLinkResponse]:
    try:
        links = list_document_links(
            session,
            user_id=current_user.id,
            document_id=document_id,
        )
    except (AuthorizationError, DocumentNotFoundError) as exc:
        raise _translate_service_error(exc) from exc
    return [DocumentLinkResponse.model_validate(link) for link in links]


@router.post(
    "/{document_id}/links",
    response_model=DocumentLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_link_endpoint(
    document_id: UUID,
    payload: DocumentLinkCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentLinkResponse:
    try:
        link = add_document_link(
            session,
            actor=current_user,
            document_id=document_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
    except (
        AuthorizationError,
        DocumentNotFoundError,
        DocumentLinkTargetNotFoundError,
        DocumentStateConflictError,
        DocumentLinkConflictError,
    ) as exc:
        raise _translate_service_error(exc) from exc
    return DocumentLinkResponse.model_validate(link)


@router.delete("/{document_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_link_endpoint(
    document_id: UUID,
    link_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        unlink_document(
            session,
            actor=current_user,
            document_id=document_id,
            link_id=link_id,
        )
    except (
        AuthorizationError,
        DocumentNotFoundError,
        DocumentLinkNotFoundError,
        DocumentStateConflictError,
    ) as exc:
        raise _translate_service_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{document_id}/permissions",
    response_model=list[DocumentPermissionResponse],
)
def read_document_permissions(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[DocumentPermissionResponse]:
    try:
        permissions = list_document_permissions(
            session,
            user_id=current_user.id,
            document_id=document_id,
        )
    except (AuthorizationError, DocumentNotFoundError) as exc:
        raise _translate_service_error(exc) from exc
    return [DocumentPermissionResponse.model_validate(item) for item in permissions]


@router.post(
    "/{document_id}/permissions",
    response_model=DocumentPermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_permission_endpoint(
    document_id: UUID,
    payload: DocumentPermissionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> DocumentPermissionResponse:
    try:
        permission = grant_document_permission(
            session,
            actor=current_user,
            document_id=document_id,
            role_id=payload.role_id,
            permission_type=payload.permission_type,
        )
    except (
        AuthorizationError,
        DocumentNotFoundError,
        DocumentPermissionTargetNotFoundError,
        DocumentPermissionConflictError,
    ) as exc:
        raise _translate_service_error(exc) from exc
    return DocumentPermissionResponse.model_validate(permission)


@router.delete(
    "/{document_id}/permissions/{document_permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document_permission_endpoint(
    document_id: UUID,
    document_permission_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        revoke_document_permission(
            session,
            actor=current_user,
            document_id=document_id,
            document_permission_id=document_permission_id,
        )
    except (
        AuthorizationError,
        DocumentNotFoundError,
        DocumentPermissionNotFoundError,
        DocumentPermissionConflictError,
    ) as exc:
        raise _translate_service_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document_version(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageProvider, Depends(get_document_storage)],
    file: Annotated[UploadFile, File(...)],
) -> DocumentVersionResponse:
    # Read one byte beyond the configured maximum so oversized uploads are
    # rejected without accepting unbounded content into memory.
    content = await file.read(settings.documents_max_file_size_bytes + 1)
    try:
        version = create_document_version(
            session,
            actor=current_user,
            document_id=document_id,
            filename=file.filename,
            declared_content_type=file.content_type,
            content=content,
            max_size_bytes=settings.documents_max_file_size_bytes,
            storage=storage,
        )
    except (
        AuthorizationError,
        DocumentNotFoundError,
        DocumentUploadValidationError,
        DocumentStateConflictError,
    ) as exc:
        raise _translate_service_error(exc) from exc
    finally:
        await file.close()

    # The service already authorized and committed this exact version. Response
    # shaping must not introduce a second documents.read requirement after a
    # successful documents.manage mutation.
    return DocumentVersionResponse.model_validate(version_to_response_data(version))


@router.get("/{document_id}/download")
def download_document_endpoint(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageProvider, Depends(get_document_storage)],
) -> StreamingResponse:
    try:
        downloaded = download_latest_document(
            session,
            actor=current_user,
            document_id=document_id,
            storage=storage,
        )
    except (AuthorizationError, DocumentNotFoundError) as exc:
        raise _translate_service_error(exc) from exc
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document file is unavailable or failed integrity validation.",
        ) from exc

    encoded_filename = quote(downloaded.file_name, safe="")
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"document\"; filename*=UTF-8''{encoded_filename}"
        ),
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(
        BytesIO(downloaded.content),
        media_type=downloaded.mime_type,
        headers=headers,
    )
