from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.access.policy import AuthorizationError
from app.core.identity.dependencies import get_current_user
from app.core.identity.models import User
from app.core.workflow.models import WorkflowInstanceStatus
from app.core.workflow.schemas import (
    WorkflowDefinitionCreateRequest,
    WorkflowDefinitionResponse,
    WorkflowDefinitionUpdateRequest,
    WorkflowInstanceCreateRequest,
    WorkflowInstanceResponse,
    WorkflowInstanceTransitionRequest,
    WorkflowOrganizationCapabilityResponse,
    WorkflowStateCreateRequest,
    WorkflowStateUpdateRequest,
    WorkflowTransitionCreateRequest,
    WorkflowTransitionUpdateRequest,
)
from app.core.workflow.service import (
    WorkflowConflictError,
    WorkflowNotFoundError,
    WorkflowValidationError,
    add_state,
    add_transition,
    cancel_instance,
    create_definition,
    create_new_version,
    delete_state,
    delete_transition,
    get_definition_for_user,
    get_instance_for_user,
    list_definitions_for_user,
    list_instances_for_user,
    list_workflow_organizations_for_user,
    publish_definition,
    retire_definition,
    start_instance,
    transition_instance,
    update_definition,
    update_state,
    update_transition,
)
from app.db.session import get_db

router = APIRouter(prefix="/workflow", tags=["workflow"])


def _translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
    if isinstance(exc, WorkflowNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, WorkflowConflictError) or isinstance(exc, IntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc) if not isinstance(exc, IntegrityError) else "Workflow write conflict.")
    if isinstance(exc, WorkflowValidationError) or isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get("/organizations", response_model=list[WorkflowOrganizationCapabilityResponse])
def list_workflow_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> list[WorkflowOrganizationCapabilityResponse]:
    items = list_workflow_organizations_for_user(session, user_id=current_user.id)
    return [WorkflowOrganizationCapabilityResponse.model_validate(item) for item in items]


@router.get("/definitions", response_model=list[WorkflowDefinitionResponse])
def list_workflow_definitions(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    include_drafts: bool = False,
) -> list[WorkflowDefinitionResponse]:
    try:
        definitions = list_definitions_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            include_drafts=include_drafts,
        )
    except AuthorizationError as exc:
        raise _translate_error(exc) from exc
    return [WorkflowDefinitionResponse.model_validate(item) for item in definitions]


@router.post("/definitions", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_workflow_definition(
    payload: WorkflowDefinitionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = create_definition(session, actor=current_user, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.get("/definitions/{definition_id}", response_model=WorkflowDefinitionResponse)
def get_workflow_definition(
    definition_id: UUID,
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = get_definition_for_user(
            session,
            user_id=current_user.id,
            definition_id=definition_id,
            organization_id=organization_id,
        )
    except (AuthorizationError, WorkflowNotFoundError) as exc:
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.patch("/definitions/{definition_id}", response_model=WorkflowDefinitionResponse)
def update_workflow_definition(
    definition_id: UUID,
    payload: WorkflowDefinitionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = update_definition(session, actor=current_user, definition_id=definition_id, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.post("/definitions/{definition_id}/states", response_model=WorkflowDefinitionResponse)
def add_workflow_state(
    definition_id: UUID,
    payload: WorkflowStateCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = add_state(session, actor=current_user, definition_id=definition_id, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.patch("/definitions/{definition_id}/states/{state_id}", response_model=WorkflowDefinitionResponse)
def update_workflow_state(
    definition_id: UUID,
    state_id: UUID,
    payload: WorkflowStateUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = update_state(session, actor=current_user, definition_id=definition_id, state_id=state_id, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.delete("/definitions/{definition_id}/states/{state_id}", response_model=WorkflowDefinitionResponse)
def delete_workflow_state(
    definition_id: UUID,
    state_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = delete_state(session, actor=current_user, definition_id=definition_id, state_id=state_id)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.post("/definitions/{definition_id}/transitions", response_model=WorkflowDefinitionResponse)
def add_workflow_transition(
    definition_id: UUID,
    payload: WorkflowTransitionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = add_transition(session, actor=current_user, definition_id=definition_id, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.patch("/definitions/{definition_id}/transitions/{transition_id}", response_model=WorkflowDefinitionResponse)
def update_workflow_transition(
    definition_id: UUID,
    transition_id: UUID,
    payload: WorkflowTransitionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = update_transition(session, actor=current_user, definition_id=definition_id, transition_id=transition_id, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.delete("/definitions/{definition_id}/transitions/{transition_id}", response_model=WorkflowDefinitionResponse)
def delete_workflow_transition(
    definition_id: UUID,
    transition_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = delete_transition(session, actor=current_user, definition_id=definition_id, transition_id=transition_id)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.post("/definitions/{definition_id}/publish", response_model=WorkflowDefinitionResponse)
def publish_workflow_definition(
    definition_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = publish_definition(session, actor=current_user, definition_id=definition_id)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.post("/definitions/{definition_id}/retire", response_model=WorkflowDefinitionResponse)
def retire_workflow_definition(
    definition_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = retire_definition(session, actor=current_user, definition_id=definition_id)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.post("/definitions/{definition_id}/new-version", response_model=WorkflowDefinitionResponse, status_code=status.HTTP_201_CREATED)
def new_workflow_definition_version(
    definition_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowDefinitionResponse:
    try:
        item = create_new_version(session, actor=current_user, definition_id=definition_id)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowDefinitionResponse.model_validate(item)


@router.get("/instances", response_model=list[WorkflowInstanceResponse])
def list_workflow_instances(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    resource_type: str | None = None,
    resource_id: str | None = None,
    instance_status: WorkflowInstanceStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[WorkflowInstanceResponse]:
    try:
        items = list_instances_for_user(
            session,
            user_id=current_user.id,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            status=instance_status,
            limit=limit,
            offset=offset,
        )
    except AuthorizationError as exc:
        raise _translate_error(exc) from exc
    return [WorkflowInstanceResponse.model_validate(item) for item in items]


@router.post("/instances", response_model=WorkflowInstanceResponse, status_code=status.HTTP_201_CREATED)
def create_workflow_instance(
    payload: WorkflowInstanceCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowInstanceResponse:
    try:
        item = start_instance(session, actor=current_user, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowInstanceResponse.model_validate(item)


@router.get("/instances/{instance_id}", response_model=WorkflowInstanceResponse)
def get_workflow_instance(
    instance_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowInstanceResponse:
    try:
        item = get_instance_for_user(session, user_id=current_user.id, instance_id=instance_id)
    except WorkflowNotFoundError as exc:
        raise _translate_error(exc) from exc
    return WorkflowInstanceResponse.model_validate(item)


@router.post("/instances/{instance_id}/transition", response_model=WorkflowInstanceResponse)
def transition_workflow_instance(
    instance_id: UUID,
    payload: WorkflowInstanceTransitionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowInstanceResponse:
    try:
        item = transition_instance(session, actor=current_user, instance_id=instance_id, payload=payload)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowInstanceResponse.model_validate(item)


@router.post("/instances/{instance_id}/cancel", response_model=WorkflowInstanceResponse)
def cancel_workflow_instance(
    instance_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> WorkflowInstanceResponse:
    try:
        item = cancel_instance(session, actor=current_user, instance_id=instance_id)
    except (AuthorizationError, WorkflowNotFoundError, WorkflowConflictError, WorkflowValidationError, ValueError, IntegrityError) as exc:
        session.rollback()
        raise _translate_error(exc) from exc
    return WorkflowInstanceResponse.model_validate(item)
