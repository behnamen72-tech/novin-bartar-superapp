from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.workflow.models import WorkflowTransitionRecord


class WorkflowHistoryIntegrityError(ValueError):
    pass


@event.listens_for(Session, "before_flush")
def prevent_workflow_history_mutation(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances

    for obj in session.dirty:
        if not isinstance(obj, WorkflowTransitionRecord) or obj in session.new:
            continue
        state = inspect(obj)
        if state.persistent and state.modified:
            raise WorkflowHistoryIntegrityError(
                "Workflow transition history is immutable and cannot be updated."
            )

    for obj in session.deleted:
        if isinstance(obj, WorkflowTransitionRecord):
            raise WorkflowHistoryIntegrityError(
                "Workflow transition history is immutable and cannot be deleted."
            )
