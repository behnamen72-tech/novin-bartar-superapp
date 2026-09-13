import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.customers.models import CommercialStatus, CustomerSource, CustomerType


class CRMOrganizationCapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    organization_type: str
    parent_id: UUID | None
    is_active: bool
    can_read: bool
    can_manage: bool
    can_read_notes: bool
    can_manage_notes: bool
    can_assign: bool
    can_manage_tags: bool
    can_read_commerce_activity: bool


class CRMAssigneeOptionResponse(BaseModel):
    id: UUID
    email: str
    display_name: str


class CustomerCRMCreateRequest(BaseModel):
    organization_id: UUID
    commerce_customer_ref: str = Field(min_length=1, max_length=128)
    customer_type: CustomerType = CustomerType.INDIVIDUAL
    commercial_status: CommercialStatus = CommercialStatus.PROSPECT
    source: CustomerSource = CustomerSource.MANUAL
    display_label: str = Field(min_length=1, max_length=200)

    @field_validator("commerce_customer_ref")
    @classmethod
    def normalize_commerce_ref(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Commerce customer reference cannot be empty.")
        if re.fullmatch(r"[A-Za-z0-9._:-]+", normalized) is None:
            raise ValueError("Commerce customer reference contains invalid characters.")
        return normalized

    @field_validator("display_label")
    @classmethod
    def normalize_display_label(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Display label cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def reject_archived_create(self) -> "CustomerCRMCreateRequest":
        if self.commercial_status is CommercialStatus.ARCHIVED:
            raise ValueError("Create an active CRM record before archiving it.")
        return self


class CustomerCRMUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    customer_type: CustomerType | None = None
    commercial_status: CommercialStatus | None = None
    source: CustomerSource | None = None
    display_label: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("display_label")
    @classmethod
    def normalize_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "CustomerCRMUpdateRequest":
        for field_name in ("customer_type", "commercial_status", "source", "display_label"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class CustomerCRMStatusRequest(BaseModel):
    expected_version: int = Field(ge=1)
    is_active: bool


class CustomerAssignmentRequest(BaseModel):
    expected_version: int = Field(ge=1)
    assigned_owner_user_id: UUID


class CustomerUnassignRequest(BaseModel):
    expected_version: int = Field(ge=1)


class CustomerTagCreateRequest(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Tag name cannot be empty.")
        return normalized


class CustomerTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    is_active: bool


class CustomerCRMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    commerce_customer_ref: str
    customer_type: CustomerType
    commercial_status: CommercialStatus
    source: CustomerSource
    display_label: str
    assigned_owner_user_id: UUID | None
    created_by_user_id: UUID
    is_active: bool
    version: int
    tags: list[CustomerTagResponse] = Field(default_factory=list)


class CustomerNoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Note body cannot be empty.")
        return normalized


class CustomerNoteUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Note body cannot be empty.")
        return normalized


class CustomerNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_crm_record_id: UUID
    author_user_id: UUID
    body: str
    version: int
    created_at: datetime
    updated_at: datetime


class CommerceCustomerValidationResult(BaseModel):
    exists: bool
    display_label: str | None = Field(default=None, max_length=200)
    has_commercial_relationship: bool | None = None
    last_interaction_at: datetime | None = None


class CommerceActivityItem(BaseModel):
    external_order_ref: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    total_amount_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=8)


class CommerceActivityProjection(BaseModel):
    source_updated_at: datetime | None = None
    orders: list[CommerceActivityItem] = Field(default_factory=list, max_length=20)
