from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.notifications.models import NotificationSeverity


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    recipient_user_id: UUID
    organization_id: UUID | None
    event_code: str
    source: str
    severity: NotificationSeverity
    title: str
    body: str | None
    resource_type: str | None
    resource_id: str | None
    action_path: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int = Field(ge=0)


class NotificationReadAllResponse(BaseModel):
    marked_read: int = Field(ge=0)
