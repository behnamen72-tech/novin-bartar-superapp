from typing import Any

from sqlalchemy import event, inspect

from app.core.notifications.models import Notification


class NotificationIntegrityError(ValueError):
    pass


@event.listens_for(Notification, "before_update")
def prevent_notification_content_mutation(
    mapper: Any, connection: Any, target: Notification
) -> None:  # noqa: ARG001
    state = inspect(target)
    changed = {attribute.key for attribute in state.attrs if attribute.history.has_changes()}
    illegal = changed - {"read_at"}
    if illegal:
        raise NotificationIntegrityError(
            "Notification content and ownership are immutable after creation."
        )


@event.listens_for(Notification, "before_delete")
def prevent_notification_delete(mapper: Any, connection: Any, target: Notification) -> None:  # noqa: ARG001
    raise NotificationIntegrityError("Notifications cannot be physically deleted.")
