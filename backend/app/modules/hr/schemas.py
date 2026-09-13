from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.access.models import OrganizationScopeMode
from app.modules.hr.models import EmploymentType


class HROrganizationCapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    organization_type: str
    parent_id: UUID | None
    is_active: bool
    can_read: bool
    can_manage: bool


class HRJobProfileCreateRequest(BaseModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    scope_mode: OrganizationScopeMode = OrganizationScopeMode.SELF

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper().replace(" ", "-")
        if not normalized:
            raise ValueError("Job profile code cannot be empty.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("Job profile code contains invalid characters.")
        return normalized

    @field_validator("title", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class HRJobProfileUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=1000)
    scope_mode: OrganizationScopeMode | None = None

    @field_validator("title", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "HRJobProfileUpdateRequest":
        for field_name in ("title", "scope_mode"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class HRStatusRequest(BaseModel):
    is_active: bool


class HRJobProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    code: str
    title: str
    description: str | None
    scope_mode: OrganizationScopeMode
    is_active: bool


class HRPositionCreateRequest(BaseModel):
    organization_id: UUID
    job_profile_id: UUID
    code: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=180)
    reports_to_position_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper().replace(" ", "-")
        if not normalized:
            raise ValueError("Position code cannot be empty.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("Position code contains invalid characters.")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class HRPositionUpdateRequest(BaseModel):
    job_profile_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=180)
    reports_to_position_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper().replace(" ", "-")
        if not normalized:
            raise ValueError("Position code cannot be empty.")
        if not all(ch.isalnum() or ch in "-_." for ch in normalized):
            raise ValueError("Position code contains invalid characters.")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def reject_required_nulls(self) -> "HRPositionUpdateRequest":
        for field_name in ("job_profile_id", "code"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class HRJobProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    title: str
    organization_id: UUID
    is_active: bool


class HRPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    job_profile_id: UUID
    code: str
    name: str | None
    reports_to_position_id: UUID | None
    is_active: bool
    job_profile: HRJobProfileSummary


class HRPersonOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str


class HREmploymentCreateRequest(BaseModel):
    organization_id: UUID
    person_id: UUID
    position_id: UUID | None = None
    employment_number: str | None = Field(default=None, max_length=80)
    employment_type: EmploymentType = EmploymentType.OTHER
    start_date: date

    @field_validator("employment_number")
    @classmethod
    def normalize_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class HREmploymentUpdateRequest(BaseModel):
    position_id: UUID | None = None
    employment_number: str | None = Field(default=None, max_length=80)
    employment_type: EmploymentType | None = None
    start_date: date | None = None

    @field_validator("employment_number")
    @classmethod
    def normalize_number(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @model_validator(mode="after")
    def reject_required_nulls(self) -> "HREmploymentUpdateRequest":
        for field_name in ("employment_type", "start_date"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class HREmploymentStatusRequest(BaseModel):
    is_active: bool
    end_date: date | None = None


class HRPersonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    is_active: bool


class HRPositionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str | None
    is_active: bool


class HREmploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    person_id: UUID
    position_id: UUID | None
    employment_number: str | None
    employment_type: EmploymentType
    start_date: date
    end_date: date | None
    is_active: bool
    person: HRPersonSummary
    position: HRPositionSummary | None
