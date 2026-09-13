from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.access.models import OrganizationScopeMode
from app.core.workflow.models import WorkflowDefinitionStatus, WorkflowInstanceStatus


class WorkflowOrganizationCapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    organization_type: str
    parent_id: UUID | None
    is_active: bool
    can_read: bool
    can_manage: bool
    can_execute: bool


class WorkflowDefinitionCreateRequest(BaseModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    scope_mode: OrganizationScopeMode = OrganizationScopeMode.SELF

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("Workflow code cannot be empty.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("Workflow code contains invalid characters.")
        return normalized

    @field_validator("name", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WorkflowDefinitionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    scope_mode: OrganizationScopeMode | None = None

    @field_validator("name", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def reject_null_name_or_scope(self) -> "WorkflowDefinitionUpdateRequest":
        for field_name in ("name", "scope_mode"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class WorkflowStateCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    position: int = Field(default=0, ge=0)
    is_initial: bool = False
    is_terminal: bool = False

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("State code cannot be empty.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("State code contains invalid characters.")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("State name cannot be empty.")
        return normalized


class WorkflowStateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    position: int | None = Field(default=None, ge=0)
    is_initial: bool | None = None
    is_terminal: bool | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "WorkflowStateUpdateRequest":
        for field_name in ("name", "position", "is_initial", "is_terminal"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        if self.name is not None:
            self.name = self.name.strip()
        return self


class WorkflowTransitionCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)
    from_state_id: UUID
    to_state_id: UUID

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().lower().replace(" ", "-")
        if not normalized:
            raise ValueError("Transition code cannot be empty.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("Transition code contains invalid characters.")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Transition name cannot be empty.")
        return normalized


class WorkflowTransitionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    from_state_id: UUID | None = None
    to_state_id: UUID | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "WorkflowTransitionUpdateRequest":
        for field_name in ("name", "from_state_id", "to_state_id"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        if self.name is not None:
            self.name = self.name.strip()
        return self


class WorkflowStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    position: int
    is_initial: bool
    is_terminal: bool


class WorkflowTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    from_state_id: UUID
    to_state_id: UUID


class WorkflowDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    version: int
    scope_mode: OrganizationScopeMode
    status: WorkflowDefinitionStatus
    states: list[WorkflowStateResponse] = Field(default_factory=list)
    transitions: list[WorkflowTransitionResponse] = Field(default_factory=list)


class WorkflowInstanceCreateRequest(BaseModel):
    definition_id: UUID
    organization_id: UUID
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: str = Field(min_length=1, max_length=160)

    @field_validator("resource_type")
    @classmethod
    def normalize_resource_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or not normalized[0].isalpha():
            raise ValueError("resource_type must start with a letter.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("resource_type contains invalid characters.")
        return normalized

    @field_validator("resource_id")
    @classmethod
    def normalize_resource_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("resource_id cannot be empty.")
        return normalized


class WorkflowInstanceTransitionRequest(BaseModel):
    transition_id: UUID
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WorkflowTransitionRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transition_id: UUID
    from_state_id: UUID
    to_state_id: UUID
    actor_user_id: UUID
    comment: str | None
    occurred_at: datetime


class WorkflowInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    definition_id: UUID
    organization_id: UUID
    resource_type: str
    resource_id: str
    current_state_id: UUID
    status: WorkflowInstanceStatus
    started_by_user_id: UUID
    completed_at: datetime | None
    cancelled_at: datetime | None
    history: list[WorkflowTransitionRecordResponse] = Field(default_factory=list)
