from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.access.models import OrganizationScopeMode


class AccessOverviewItem(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str
    user_name: str
    role_code: str
    role_name: str
    organization_id: UUID
    organization_name: str
    scope_mode: OrganizationScopeMode
    is_active: bool
    permissions: list[str]


class PermissionCatalogItem(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class RoleAdminItem(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    organization_id: UUID | None
    organization_name: str | None
    is_system: bool
    is_active: bool
    permissions: list[str]


class RoleCreateRequest(BaseModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Role code cannot be empty.")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Role name cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Role name cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def reject_null_name(self) -> "RoleUpdateRequest":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null.")
        return self


class RoleStatusRequest(BaseModel):
    is_active: bool


class AccessAssignmentCreateRequest(BaseModel):
    user_id: UUID
    role_id: UUID
    organization_id: UUID
    scope_mode: OrganizationScopeMode = OrganizationScopeMode.SELF
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "AccessAssignmentCreateRequest":
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be later than starts_at.")
        return self


class AccessAssignmentStatusRequest(BaseModel):
    is_active: bool


class AccessAssignmentItem(BaseModel):
    id: UUID
    user_id: UUID
    role_id: UUID
    role_code: str
    organization_id: UUID
    organization_name: str
    scope_mode: OrganizationScopeMode
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
