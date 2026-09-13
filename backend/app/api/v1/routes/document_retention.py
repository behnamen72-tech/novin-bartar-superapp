from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.documents.schemas import (
    RetentionPolicyCreateRequest,
    RetentionPolicyResponse,
    RetentionPolicyUpdateRequest,
)
from app.core.documents.service import (
    DocumentMetadataValidationError,
    RetentionPolicyConflictError,
    RetentionPolicyNotFoundError,
    create_retention_policy,
    deactivate_retention_policy,
    list_retention_policies,
    restore_retention_policy,
    update_retention_policy,
)
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.db.session import get_db

router = APIRouter(prefix="/document-retention-policies", tags=["document-retention"])


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, RetentionPolicyNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, RetentionPolicyConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, DocumentMetadataValidationError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("", response_model=list[RetentionPolicyResponse])
def read_retention_policies(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    organization_id: UUID | None = None,
    include_inactive: bool = False,
) -> list[RetentionPolicyResponse]:
    try:
        policies = list_retention_policies(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_inactive=include_inactive,
        )
    except AuthorizationError as exc:
        raise _translate(exc) from exc
    return [RetentionPolicyResponse.model_validate(item) for item in policies]


@router.post("", response_model=RetentionPolicyResponse, status_code=status.HTTP_201_CREATED)
def create_retention_policy_endpoint(
    payload: RetentionPolicyCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RetentionPolicyResponse:
    try:
        policy = create_retention_policy(
            session,
            actor=current_user,
            organization_id=payload.organization_id,
            code=payload.code,
            name=payload.name,
            description=payload.description,
            retention_days=payload.retention_days,
            basis=payload.basis,
        )
    except (
        AuthorizationError,
        RetentionPolicyConflictError,
        DocumentMetadataValidationError,
    ) as exc:
        raise _translate(exc) from exc
    return RetentionPolicyResponse.model_validate(policy)


@router.patch("/{retention_policy_id}", response_model=RetentionPolicyResponse)
def update_retention_policy_endpoint(
    retention_policy_id: UUID,
    payload: RetentionPolicyUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RetentionPolicyResponse:
    try:
        policy = update_retention_policy(
            session,
            actor=current_user,
            retention_policy_id=retention_policy_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except (
        AuthorizationError,
        RetentionPolicyNotFoundError,
        RetentionPolicyConflictError,
        DocumentMetadataValidationError,
    ) as exc:
        raise _translate(exc) from exc
    return RetentionPolicyResponse.model_validate(policy)


@router.delete("/{retention_policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_retention_policy_endpoint(
    retention_policy_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        deactivate_retention_policy(
            session,
            actor=current_user,
            retention_policy_id=retention_policy_id,
        )
    except (AuthorizationError, RetentionPolicyNotFoundError) as exc:
        raise _translate(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{retention_policy_id}/restore", response_model=RetentionPolicyResponse)
def restore_retention_policy_endpoint(
    retention_policy_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> RetentionPolicyResponse:
    try:
        policy = restore_retention_policy(
            session,
            actor=current_user,
            retention_policy_id=retention_policy_id,
        )
    except (AuthorizationError, RetentionPolicyNotFoundError) as exc:
        raise _translate(exc) from exc
    return RetentionPolicyResponse.model_validate(policy)
