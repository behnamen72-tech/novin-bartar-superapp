from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.organization.hierarchy import validate_parent_type
from app.core.organization.models import Organization


@event.listens_for(Session, "before_flush")
def validate_organization_hierarchy_before_flush(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    del flush_context, instances

    candidates = {
        obj
        for obj in session.new.union(session.dirty)
        if isinstance(obj, Organization)
    }

    for organization in candidates:
        parent = organization.parent

        if parent is None and organization.parent_id is not None:
            parent = session.get(Organization, organization.parent_id)

        if organization.parent_id is not None and parent is None:
            raise ValueError(
                f"Parent organization {organization.parent_id} does not exist."
            )

        parent_type = parent.organization_type if parent is not None else None
        validate_parent_type(
            child_type=organization.organization_type,
            parent_type=parent_type,
        )
