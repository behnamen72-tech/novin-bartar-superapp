from sqlalchemy import event, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper

from app.core.notifications.models import Notification


class NotificationIntegrityError(ValueError):
    pass


@event.listens_for(Notification, "before_update")
def prevent_notification_content_mutation(
    _mapper: Mapper[Notification], _connection: Connection, target: Notification
) -> None:
    state = inspect(target)
    changed = {attribute.key for attribute in state.attrs if attribute.history.has_changes()}
    illegal = changed - {"read_at"}
    if illegal:
        raise NotificationIntegrityError(
            "Notification content and ownership are immutable after creation."
        )


@event.listens_for(Notification, "before_delete")
def prevent_notification_delete(
    _mapper: Mapper[Notification], _connection: Connection, target: Notification
) -> None:
    raise NotificationIntegrityError("Notifications cannot be physically deleted.")
