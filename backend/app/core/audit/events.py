from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.audit.models import AuditEvent


class AuditIntegrityError(ValueError):
    pass


@event.listens_for(Session, "before_flush")
def prevent_audit_event_mutation(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances

    for obj in session.dirty:
        if not isinstance(obj, AuditEvent):
            continue
        if obj in session.new:
            continue
        state = inspect(obj)
        if state.persistent and state.modified:
            raise AuditIntegrityError("Audit events are immutable and cannot be updated.")

    for obj in session.deleted:
        if isinstance(obj, AuditEvent):
            raise AuditIntegrityError("Audit events are immutable and cannot be deleted.")
