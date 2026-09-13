from uuid import UUID

from pydantic import BaseModel

from app.core.access.models import OrganizationScopeMode


class PermissionCheckResponse(BaseModel):
    organization_id: UUID
    permission: str
    allowed: bool


class MyAccessAssignmentResponse(BaseModel):
    role_code: str
    organization_id: UUID
    organization_name: str
    scope_mode: OrganizationScopeMode
    permissions: list[str]
