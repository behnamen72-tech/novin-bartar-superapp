from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.access.permissions import WORKFLOW_EXECUTE, WORKFLOW_MANAGE, WORKFLOW_READ
from app.core.access.policy import (
    has_permission,
    organization_is_in_scope,
    require_permission_for_organization,
)
from app.core.audit.service import record_audit_event
from app.core.identity.models import User
from app.core.notifications.models import NotificationSeverity
from app.core.notifications.service import create_notification
from app.core.organization.models import Organization
from app.core.workflow.models import (
    WorkflowDefinition,
    WorkflowDefinitionStatus,
    WorkflowInstance,
    WorkflowInstanceStatus,
    WorkflowState,
    WorkflowTransition,
    WorkflowTransitionRecord,
)
from app.core.workflow.schemas import (
    WorkflowDefinitionCreateRequest,
    WorkflowDefinitionUpdateRequest,
    WorkflowInstanceCreateRequest,
    WorkflowInstanceTransitionRequest,
    WorkflowStateCreateRequest,
    WorkflowStateUpdateRequest,
    WorkflowTransitionCreateRequest,
    WorkflowTransitionUpdateRequest,
)


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowConflictError(ValueError):
    pass


class WorkflowValidationError(ValueError):
    pass


def _definition_options():
    return (
        selectinload(WorkflowDefinition.states),
        selectinload(WorkflowDefinition.transitions),
    )


def _instance_options():
    return (
        selectinload(WorkflowInstance.history),
        selectinload(WorkflowInstance.definition),
        selectinload(WorkflowInstance.current_state),
    )


def list_workflow_organizations_for_user(
    session: Session,
    *,
    user_id: UUID,
) -> list[dict[str, object]]:
    """Return active organizations with the actor's effective workflow capabilities.

    This deliberately does not depend on organization.read. Workflow permissions are
    independently scoped capabilities, so the Workflow UI can discover only the
    organizations where one of those capabilities is already effective.
    """
    organizations = list(
        session.scalars(
            select(Organization)
            .where(Organization.is_active.is_(True))
            .order_by(Organization.name, Organization.id)
        ).all()
    )
    result: list[dict[str, object]] = []
    for organization in organizations:
        can_read = has_permission(
            session,
            user_id=user_id,
            permission_code=WORKFLOW_READ,
            organization_id=organization.id,
        )
        can_manage = has_permission(
            session,
            user_id=user_id,
            permission_code=WORKFLOW_MANAGE,
            organization_id=organization.id,
        )
        can_execute = has_permission(
            session,
            user_id=user_id,
            permission_code=WORKFLOW_EXECUTE,
            organization_id=organization.id,
        )
        if not (can_read or can_manage or can_execute):
            continue
        result.append(
            {
                "id": organization.id,
                "name": organization.name,
                "code": organization.code,
                "organization_type": organization.organization_type.value,
                "parent_id": organization.parent_id,
                "is_active": organization.is_active,
                "can_read": can_read,
                "can_manage": can_manage,
                "can_execute": can_execute,
            }
        )
    return result


def _get_definition(
    session: Session, definition_id: UUID, *, lock: bool = False
) -> WorkflowDefinition:
    statement = (
        select(WorkflowDefinition)
        .where(WorkflowDefinition.id == definition_id)
        .options(*_definition_options())
    )
    if lock:
        statement = statement.with_for_update()
    definition = session.scalar(statement)
    if definition is None:
        raise WorkflowNotFoundError("Workflow definition not found.")
    return definition


def _require_manage_definition(
    session: Session, *, actor: User, definition: WorkflowDefinition
) -> None:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=WORKFLOW_MANAGE,
        organization_id=definition.organization_id,
    )


def _require_draft(definition: WorkflowDefinition) -> None:
    if definition.status is not WorkflowDefinitionStatus.DRAFT:
        raise WorkflowConflictError(
            "Published or retired workflow definitions are immutable; create a new version instead."
        )


def _definition_applies_to_organization(
    session: Session,
    *,
    definition: WorkflowDefinition,
    organization_id: UUID,
) -> bool:
    return organization_is_in_scope(
        session,
        scope_organization_id=definition.organization_id,
        scope_mode=definition.scope_mode,
        target_organization_id=organization_id,
    )


def list_definitions_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    include_drafts: bool = False,
) -> list[WorkflowDefinition]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=WORKFLOW_READ,
        organization_id=organization_id,
    )
    can_manage_target = has_permission(
        session,
        user_id=user_id,
        permission_code=WORKFLOW_MANAGE,
        organization_id=organization_id,
    )
    definitions = list(
        session.scalars(
            select(WorkflowDefinition)
            .options(*_definition_options())
            .order_by(WorkflowDefinition.code, WorkflowDefinition.version.desc())
        ).all()
    )
    result: list[WorkflowDefinition] = []
    for definition in definitions:
        if (
            definition.status is WorkflowDefinitionStatus.PUBLISHED
            and _definition_applies_to_organization(
                session, definition=definition, organization_id=organization_id
            )
        ):
            result.append(definition)
            continue
        if (
            include_drafts
            and can_manage_target
            and definition.organization_id == organization_id
            and definition.status
            in {WorkflowDefinitionStatus.DRAFT, WorkflowDefinitionStatus.RETIRED}
        ):
            result.append(definition)
    return result


def get_definition_for_user(
    session: Session,
    *,
    user_id: UUID,
    definition_id: UUID,
    organization_id: UUID,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id)
    if not has_permission(
        session,
        user_id=user_id,
        permission_code=WORKFLOW_READ,
        organization_id=organization_id,
    ):
        raise WorkflowNotFoundError("Workflow definition not found.")
    if definition.status is WorkflowDefinitionStatus.PUBLISHED:
        if not _definition_applies_to_organization(
            session, definition=definition, organization_id=organization_id
        ):
            raise WorkflowNotFoundError("Workflow definition not found.")
    elif definition.organization_id != organization_id or not has_permission(
        session,
        user_id=user_id,
        permission_code=WORKFLOW_MANAGE,
        organization_id=organization_id,
    ):
        raise WorkflowNotFoundError("Workflow definition not found.")
    return definition


def create_definition(
    session: Session,
    *,
    actor: User,
    payload: WorkflowDefinitionCreateRequest,
) -> WorkflowDefinition:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=WORKFLOW_MANAGE,
        organization_id=payload.organization_id,
    )
    organization = session.get(Organization, payload.organization_id)
    if organization is None or not organization.is_active:
        raise WorkflowNotFoundError("Organization not found.")
    exists = session.scalar(
        select(WorkflowDefinition.id)
        .where(
            WorkflowDefinition.organization_id == payload.organization_id,
            WorkflowDefinition.code == payload.code,
        )
        .limit(1)
    )
    if exists is not None:
        raise WorkflowConflictError(
            "Workflow code already exists in this organization; create a new version instead."
        )

    definition = WorkflowDefinition(
        organization_id=payload.organization_id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        version=1,
        scope_mode=payload.scope_mode,
        status=WorkflowDefinitionStatus.DRAFT,
    )
    session.add(definition)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.definition.created",
        resource_type="workflow_definition",
        resource_id=definition.id,
        after_state={
            "code": definition.code,
            "version": definition.version,
            "name": definition.name,
            "scope_mode": definition.scope_mode.value,
            "status": definition.status.value,
        },
    )
    session.commit()
    return _get_definition(session, definition.id)


def update_definition(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    payload: WorkflowDefinitionUpdateRequest,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return definition
    before = {
        "name": definition.name,
        "description": definition.description,
        "scope_mode": definition.scope_mode.value,
    }
    for key, value in changes.items():
        setattr(definition, key, value)
    after = {
        "name": definition.name,
        "description": definition.description,
        "scope_mode": definition.scope_mode.value,
    }
    if before == after:
        return definition
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.definition.updated",
        resource_type="workflow_definition",
        resource_id=definition.id,
        before_state=before,
        after_state=after,
    )
    session.commit()
    return _get_definition(session, definition.id)


def add_state(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    payload: WorkflowStateCreateRequest,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    if any(state.code == payload.code for state in definition.states):
        raise WorkflowConflictError("State code already exists in this workflow version.")
    if payload.is_initial and any(state.is_initial for state in definition.states):
        raise WorkflowConflictError("A workflow version can have only one initial state.")
    state = WorkflowState(definition=definition, **payload.model_dump())
    session.add(state)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.state.created",
        resource_type="workflow_state",
        resource_id=state.id,
        after_state={
            "definition_id": str(definition.id),
            "code": state.code,
            "is_initial": state.is_initial,
            "is_terminal": state.is_terminal,
        },
    )
    session.commit()
    return _get_definition(session, definition.id)


def update_state(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    state_id: UUID,
    payload: WorkflowStateUpdateRequest,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    state = next((item for item in definition.states if item.id == state_id), None)
    if state is None:
        raise WorkflowNotFoundError("Workflow state not found.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_initial") is True and any(
        item.is_initial and item.id != state.id for item in definition.states
    ):
        raise WorkflowConflictError("A workflow version can have only one initial state.")
    before = {
        "name": state.name,
        "position": state.position,
        "is_initial": state.is_initial,
        "is_terminal": state.is_terminal,
    }
    for key, value in changes.items():
        setattr(state, key, value)
    after = {
        "name": state.name,
        "position": state.position,
        "is_initial": state.is_initial,
        "is_terminal": state.is_terminal,
    }
    if before != after:
        record_audit_event(
            session,
            actor=actor,
            organization_id=definition.organization_id,
            action="workflow.state.updated",
            resource_type="workflow_state",
            resource_id=state.id,
            before_state=before,
            after_state=after,
        )
        session.commit()
    return _get_definition(session, definition.id)


def delete_state(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    state_id: UUID,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    state = next((item for item in definition.states if item.id == state_id), None)
    if state is None:
        raise WorkflowNotFoundError("Workflow state not found.")
    if any(
        t.from_state_id == state.id or t.to_state_id == state.id for t in definition.transitions
    ):
        raise WorkflowConflictError("Remove transitions that reference this state first.")
    snapshot = {"definition_id": str(definition.id), "code": state.code}
    session.delete(state)
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.state.deleted",
        resource_type="workflow_state",
        resource_id=state.id,
        before_state=snapshot,
    )
    session.commit()
    return _get_definition(session, definition.id)


def _state_in_definition(definition: WorkflowDefinition, state_id: UUID) -> WorkflowState:
    state = next((item for item in definition.states if item.id == state_id), None)
    if state is None:
        raise WorkflowValidationError("Transition states must belong to the same workflow version.")
    return state


def add_transition(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    payload: WorkflowTransitionCreateRequest,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    if any(t.code == payload.code for t in definition.transitions):
        raise WorkflowConflictError("Transition code already exists in this workflow version.")
    from_state = _state_in_definition(definition, payload.from_state_id)
    _state_in_definition(definition, payload.to_state_id)
    if payload.from_state_id == payload.to_state_id:
        raise WorkflowValidationError("Self transitions are not allowed.")
    if from_state.is_terminal:
        raise WorkflowValidationError("Terminal states cannot have outgoing transitions.")
    transition = WorkflowTransition(definition=definition, **payload.model_dump())
    session.add(transition)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.transition.created",
        resource_type="workflow_transition",
        resource_id=transition.id,
        after_state={
            "definition_id": str(definition.id),
            "code": transition.code,
            "from_state_id": str(transition.from_state_id),
            "to_state_id": str(transition.to_state_id),
        },
    )
    session.commit()
    return _get_definition(session, definition.id)


def update_transition(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    transition_id: UUID,
    payload: WorkflowTransitionUpdateRequest,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    transition = next((item for item in definition.transitions if item.id == transition_id), None)
    if transition is None:
        raise WorkflowNotFoundError("Workflow transition not found.")
    changes = payload.model_dump(exclude_unset=True)
    from_id = changes.get("from_state_id", transition.from_state_id)
    to_id = changes.get("to_state_id", transition.to_state_id)
    from_state = _state_in_definition(definition, from_id)
    _state_in_definition(definition, to_id)
    if from_id == to_id:
        raise WorkflowValidationError("Self transitions are not allowed.")
    if from_state.is_terminal:
        raise WorkflowValidationError("Terminal states cannot have outgoing transitions.")
    before = {
        "name": transition.name,
        "from_state_id": str(transition.from_state_id),
        "to_state_id": str(transition.to_state_id),
    }
    for key, value in changes.items():
        setattr(transition, key, value)
    after = {
        "name": transition.name,
        "from_state_id": str(transition.from_state_id),
        "to_state_id": str(transition.to_state_id),
    }
    if before != after:
        record_audit_event(
            session,
            actor=actor,
            organization_id=definition.organization_id,
            action="workflow.transition.updated",
            resource_type="workflow_transition",
            resource_id=transition.id,
            before_state=before,
            after_state=after,
        )
        session.commit()
    return _get_definition(session, definition.id)


def delete_transition(
    session: Session,
    *,
    actor: User,
    definition_id: UUID,
    transition_id: UUID,
) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    transition = next((item for item in definition.transitions if item.id == transition_id), None)
    if transition is None:
        raise WorkflowNotFoundError("Workflow transition not found.")
    session.delete(transition)
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.transition.deleted",
        resource_type="workflow_transition",
        resource_id=transition.id,
        before_state={"definition_id": str(definition.id), "code": transition.code},
    )
    session.commit()
    return _get_definition(session, definition.id)


def _validate_publishable(definition: WorkflowDefinition) -> None:
    initial = [state for state in definition.states if state.is_initial]
    terminal = [state for state in definition.states if state.is_terminal]
    if len(initial) != 1:
        raise WorkflowValidationError("A published workflow must have exactly one initial state.")
    if not terminal:
        raise WorkflowValidationError("A published workflow must have at least one terminal state.")
    state_ids = {state.id for state in definition.states}
    state_by_id = {state.id: state for state in definition.states}
    outgoing: dict[UUID, set[UUID]] = {state.id: set() for state in definition.states}
    for transition in definition.transitions:
        if transition.from_state_id not in state_ids or transition.to_state_id not in state_ids:
            raise WorkflowValidationError(
                "Every transition must reference states from the same workflow version."
            )
        from_state = state_by_id[transition.from_state_id]
        if from_state.is_terminal:
            raise WorkflowValidationError("Terminal states cannot have outgoing transitions.")
        outgoing[transition.from_state_id].add(transition.to_state_id)

    for state in definition.states:
        if not state.is_terminal and not outgoing[state.id]:
            raise WorkflowValidationError(
                "Every non-terminal state must have at least one outgoing transition."
            )

    reachable: set[UUID] = set()
    pending = [initial[0].id]
    while pending:
        state_id = pending.pop()
        if state_id in reachable:
            continue
        reachable.add(state_id)
        pending.extend(outgoing[state_id] - reachable)
    if reachable != state_ids:
        raise WorkflowValidationError(
            "Every workflow state must be reachable from the initial state."
        )


def publish_definition(session: Session, *, actor: User, definition_id: UUID) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    _require_draft(definition)
    _validate_publishable(definition)

    existing_published = list(
        session.scalars(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.organization_id == definition.organization_id,
                WorkflowDefinition.code == definition.code,
                WorkflowDefinition.status == WorkflowDefinitionStatus.PUBLISHED,
                WorkflowDefinition.id != definition.id,
            )
            .with_for_update()
        ).all()
    )
    for previous in existing_published:
        before = {"status": previous.status.value}
        previous.status = WorkflowDefinitionStatus.RETIRED
        record_audit_event(
            session,
            actor=actor,
            organization_id=previous.organization_id,
            action="workflow.definition.retired",
            resource_type="workflow_definition",
            resource_id=previous.id,
            before_state=before,
            after_state={"status": previous.status.value},
            metadata={"replaced_by_definition_id": str(definition.id)},
        )

    definition.status = WorkflowDefinitionStatus.PUBLISHED
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.definition.published",
        resource_type="workflow_definition",
        resource_id=definition.id,
        before_state={"status": WorkflowDefinitionStatus.DRAFT.value},
        after_state={"status": definition.status.value},
    )
    session.commit()
    return _get_definition(session, definition.id)


def retire_definition(session: Session, *, actor: User, definition_id: UUID) -> WorkflowDefinition:
    definition = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=definition)
    if definition.status is WorkflowDefinitionStatus.DRAFT:
        raise WorkflowConflictError(
            "Draft workflows cannot be retired; publish them first or keep editing the draft."
        )
    if definition.status is WorkflowDefinitionStatus.RETIRED:
        return definition
    definition.status = WorkflowDefinitionStatus.RETIRED
    record_audit_event(
        session,
        actor=actor,
        organization_id=definition.organization_id,
        action="workflow.definition.retired",
        resource_type="workflow_definition",
        resource_id=definition.id,
        before_state={"status": WorkflowDefinitionStatus.PUBLISHED.value},
        after_state={"status": WorkflowDefinitionStatus.RETIRED.value},
    )
    session.commit()
    return _get_definition(session, definition.id)


def create_new_version(session: Session, *, actor: User, definition_id: UUID) -> WorkflowDefinition:
    source = _get_definition(session, definition_id, lock=True)
    _require_manage_definition(session, actor=actor, definition=source)
    if source.status is WorkflowDefinitionStatus.DRAFT:
        raise WorkflowConflictError(
            "Finish or discard the current draft before creating another version."
        )
    existing_draft = session.scalar(
        select(WorkflowDefinition.id)
        .where(
            WorkflowDefinition.organization_id == source.organization_id,
            WorkflowDefinition.code == source.code,
            WorkflowDefinition.status == WorkflowDefinitionStatus.DRAFT,
        )
        .limit(1)
    )
    if existing_draft is not None:
        raise WorkflowConflictError("A draft version already exists for this workflow code.")
    max_version = (
        session.scalar(
            select(func.max(WorkflowDefinition.version)).where(
                WorkflowDefinition.organization_id == source.organization_id,
                WorkflowDefinition.code == source.code,
            )
        )
        or 0
    )
    clone = WorkflowDefinition(
        organization_id=source.organization_id,
        code=source.code,
        name=source.name,
        description=source.description,
        version=max_version + 1,
        scope_mode=source.scope_mode,
        status=WorkflowDefinitionStatus.DRAFT,
    )
    session.add(clone)
    session.flush()
    state_map: dict[UUID, WorkflowState] = {}
    for state in sorted(source.states, key=lambda item: (item.position, item.code)):
        copied = WorkflowState(
            definition=clone,
            code=state.code,
            name=state.name,
            position=state.position,
            is_initial=state.is_initial,
            is_terminal=state.is_terminal,
        )
        session.add(copied)
        session.flush()
        state_map[state.id] = copied
    for transition in source.transitions:
        session.add(
            WorkflowTransition(
                definition=clone,
                code=transition.code,
                name=transition.name,
                from_state=state_map[transition.from_state_id],
                to_state=state_map[transition.to_state_id],
            )
        )
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=clone.organization_id,
        action="workflow.definition.version.created",
        resource_type="workflow_definition",
        resource_id=clone.id,
        after_state={"code": clone.code, "version": clone.version, "status": clone.status.value},
        metadata={"source_definition_id": str(source.id), "source_version": source.version},
    )
    session.commit()
    return _get_definition(session, clone.id)


def start_instance(
    session: Session,
    *,
    actor: User,
    payload: WorkflowInstanceCreateRequest,
) -> WorkflowInstance:
    require_permission_for_organization(
        session,
        user_id=actor.id,
        permission_code=WORKFLOW_EXECUTE,
        organization_id=payload.organization_id,
    )
    definition = _get_definition(session, payload.definition_id)
    if (
        definition.status is not WorkflowDefinitionStatus.PUBLISHED
        or not _definition_applies_to_organization(
            session, definition=definition, organization_id=payload.organization_id
        )
    ):
        raise WorkflowNotFoundError("Workflow definition not found.")
    initial = [state for state in definition.states if state.is_initial]
    if len(initial) != 1:
        raise WorkflowConflictError("Published workflow definition is invalid.")
    duplicate = session.scalar(
        select(WorkflowInstance.id)
        .where(
            WorkflowInstance.definition_id == definition.id,
            WorkflowInstance.organization_id == payload.organization_id,
            WorkflowInstance.resource_type == payload.resource_type,
            WorkflowInstance.resource_id == payload.resource_id,
        )
        .limit(1)
    )
    if duplicate is not None:
        raise WorkflowConflictError(
            "This resource already has an instance for this workflow version."
        )
    now = datetime.now(UTC)
    initial_state = initial[0]
    instance = WorkflowInstance(
        definition=definition,
        organization_id=payload.organization_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        current_state=initial_state,
        status=WorkflowInstanceStatus.COMPLETED
        if initial_state.is_terminal
        else WorkflowInstanceStatus.ACTIVE,
        started_by=actor,
        completed_at=now if initial_state.is_terminal else None,
    )
    session.add(instance)
    session.flush()
    record_audit_event(
        session,
        actor=actor,
        organization_id=instance.organization_id,
        action="workflow.instance.started",
        resource_type="workflow_instance",
        resource_id=instance.id,
        after_state={
            "definition_id": str(definition.id),
            "resource_type": instance.resource_type,
            "resource_id": instance.resource_id,
            "current_state_id": str(instance.current_state_id),
            "status": instance.status.value,
        },
    )
    session.commit()
    return _get_instance(session, instance.id)


def _get_instance(session: Session, instance_id: UUID, *, lock: bool = False) -> WorkflowInstance:
    statement = (
        select(WorkflowInstance)
        .where(WorkflowInstance.id == instance_id)
        .options(*_instance_options())
    )
    if lock:
        statement = statement.with_for_update()
    instance = session.scalar(statement)
    if instance is None:
        raise WorkflowNotFoundError("Workflow instance not found.")
    return instance


def list_instances_for_user(
    session: Session,
    *,
    user_id: UUID,
    organization_id: UUID,
    resource_type: str | None = None,
    resource_id: str | None = None,
    status: WorkflowInstanceStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[WorkflowInstance]:
    require_permission_for_organization(
        session,
        user_id=user_id,
        permission_code=WORKFLOW_READ,
        organization_id=organization_id,
    )
    statement = (
        select(WorkflowInstance)
        .where(WorkflowInstance.organization_id == organization_id)
        .options(*_instance_options())
    )
    if resource_type is not None:
        statement = statement.where(WorkflowInstance.resource_type == resource_type.strip().lower())
    if resource_id is not None:
        statement = statement.where(WorkflowInstance.resource_id == resource_id.strip())
    if status is not None:
        statement = statement.where(WorkflowInstance.status == status)
    statement = (
        statement.order_by(WorkflowInstance.created_at.desc(), WorkflowInstance.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def get_instance_for_user(
    session: Session, *, user_id: UUID, instance_id: UUID
) -> WorkflowInstance:
    instance = _get_instance(session, instance_id)
    if not has_permission(
        session,
        user_id=user_id,
        permission_code=WORKFLOW_READ,
        organization_id=instance.organization_id,
    ):
        raise WorkflowNotFoundError("Workflow instance not found.")
    return instance


def transition_instance(
    session: Session,
    *,
    actor: User,
    instance_id: UUID,
    payload: WorkflowInstanceTransitionRequest,
) -> WorkflowInstance:
    instance = _get_instance(session, instance_id, lock=True)
    if not has_permission(
        session,
        user_id=actor.id,
        permission_code=WORKFLOW_EXECUTE,
        organization_id=instance.organization_id,
    ):
        raise WorkflowNotFoundError("Workflow instance not found.")
    if instance.status is not WorkflowInstanceStatus.ACTIVE:
        raise WorkflowConflictError("Only active workflow instances can transition.")
    transition = session.scalar(
        select(WorkflowTransition).where(
            WorkflowTransition.id == payload.transition_id,
            WorkflowTransition.definition_id == instance.definition_id,
            WorkflowTransition.from_state_id == instance.current_state_id,
        )
    )
    if transition is None:
        raise WorkflowValidationError("Transition is not available from the current state.")
    to_state = session.get(WorkflowState, transition.to_state_id)
    if to_state is None:
        raise WorkflowConflictError("Workflow transition target state is missing.")

    now = datetime.now(UTC)
    before = {"current_state_id": str(instance.current_state_id), "status": instance.status.value}
    record = WorkflowTransitionRecord(
        instance=instance,
        transition=transition,
        from_state_id=instance.current_state_id,
        to_state_id=transition.to_state_id,
        actor=actor,
        comment=payload.comment,
        occurred_at=now,
    )
    session.add(record)
    instance.current_state_id = transition.to_state_id
    if to_state.is_terminal:
        instance.status = WorkflowInstanceStatus.COMPLETED
        instance.completed_at = now
    record_audit_event(
        session,
        actor=actor,
        organization_id=instance.organization_id,
        action="workflow.instance.transitioned",
        resource_type="workflow_instance",
        resource_id=instance.id,
        before_state=before,
        after_state={
            "current_state_id": str(instance.current_state_id),
            "status": instance.status.value,
        },
        metadata={"transition_id": str(transition.id), "transition_code": transition.code},
    )
    session.flush()
    if actor.id != instance.started_by_user_id:
        create_notification(
            session,
            recipient_user_id=instance.started_by_user_id,
            organization_id=instance.organization_id,
            event_code="workflow.instance.transitioned",
            source="workflow",
            severity=(
                NotificationSeverity.SUCCESS
                if instance.status is WorkflowInstanceStatus.COMPLETED
                else NotificationSeverity.INFO
            ),
            title=f"گردش‌کار «{instance.definition.name}» به‌روزرسانی شد",
            body=f"مرحله فعلی: {to_state.name}",
            resource_type="workflow_instance",
            resource_id=str(instance.id),
            action_path="/?view=workflow",
            dedupe_key=f"workflow-transition:{record.id}",
        )
    session.commit()
    return _get_instance(session, instance.id)


def cancel_instance(session: Session, *, actor: User, instance_id: UUID) -> WorkflowInstance:
    instance = _get_instance(session, instance_id, lock=True)
    if not has_permission(
        session,
        user_id=actor.id,
        permission_code=WORKFLOW_EXECUTE,
        organization_id=instance.organization_id,
    ):
        raise WorkflowNotFoundError("Workflow instance not found.")
    if instance.status is WorkflowInstanceStatus.CANCELLED:
        return instance
    if instance.status is WorkflowInstanceStatus.COMPLETED:
        raise WorkflowConflictError("Completed workflow instances cannot be cancelled.")
    before = {"status": instance.status.value}
    instance.status = WorkflowInstanceStatus.CANCELLED
    instance.cancelled_at = datetime.now(UTC)
    record_audit_event(
        session,
        actor=actor,
        organization_id=instance.organization_id,
        action="workflow.instance.cancelled",
        resource_type="workflow_instance",
        resource_id=instance.id,
        before_state=before,
        after_state={"status": instance.status.value},
    )
    if actor.id != instance.started_by_user_id:
        create_notification(
            session,
            recipient_user_id=instance.started_by_user_id,
            organization_id=instance.organization_id,
            event_code="workflow.instance.cancelled",
            source="workflow",
            severity=NotificationSeverity.WARNING,
            title=f"گردش‌کار «{instance.definition.name}» لغو شد",
            body="این گردش‌کار توسط کاربر دیگری لغو شده است.",
            resource_type="workflow_instance",
            resource_id=str(instance.id),
            action_path="/?view=workflow",
            dedupe_key=f"workflow-cancelled:{instance.id}",
        )
    session.commit()
    return _get_instance(session, instance.id)
