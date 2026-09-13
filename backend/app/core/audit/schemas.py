from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    actor_identifier: str | None
    organization_id: UUID | None
    action: str
    resource_type: str
    resource_id: str
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    event_metadata: dict[str, object] | None
    source: str
    request_id: str | None
    occurred_at: datetime
