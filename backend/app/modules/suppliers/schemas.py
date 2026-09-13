import re
import unicodedata
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.suppliers.models import (
    SupplierCommercialStatus,
    SupplierExternalSystem,
    SupplierKind,
    SupplierSource,
)


class SupplierOrganizationCapabilityResponse(BaseModel):
    id: UUID
    name: str
    code: str
    organization_type: str
    parent_id: UUID | None
    is_active: bool
    can_read: bool
    can_manage: bool
    can_read_representatives: bool
    can_manage_representatives: bool
    can_read_representative_contacts: bool
    can_read_notes: bool
    can_manage_notes: bool
    can_assign: bool
    can_manage_tag_catalog: bool
    can_assign_tags: bool
    can_read_external_references: bool
    can_manage_external_references: bool


class SupplierAssigneeOptionResponse(BaseModel):
    id: UUID
    email: str
    display_name: str


class SupplierCreateRequest(BaseModel):
    organization_id: UUID
    supplier_kind: SupplierKind = SupplierKind.COMPANY
    display_name: str = Field(min_length=1, max_length=200)
    commercial_status: SupplierCommercialStatus = SupplierCommercialStatus.PROSPECT
    source: SupplierSource = SupplierSource.MANUAL

    @field_validator("display_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Supplier display name cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def reject_archived_create(self) -> "SupplierCreateRequest":
        if self.commercial_status is SupplierCommercialStatus.ARCHIVED:
            raise ValueError("Create an active supplier before archiving it.")
        return self


class SupplierUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    supplier_kind: SupplierKind | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    commercial_status: SupplierCommercialStatus | None = None
    source: SupplierSource | None = None

    @field_validator("display_name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @model_validator(mode="after")
    def reject_nulls(self) -> "SupplierUpdateRequest":
        for field_name in ("supplier_kind", "display_name", "commercial_status", "source"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class SupplierStatusRequest(BaseModel):
    expected_version: int = Field(ge=1)
    is_active: bool


class SupplierAssignmentRequest(BaseModel):
    expected_version: int = Field(ge=1)
    assigned_owner_user_id: UUID


class SupplierUnassignRequest(BaseModel):
    expected_version: int = Field(ge=1)


class SupplierTagCreateRequest(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=60)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Tag name cannot be empty.")
        return normalized


class SupplierTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    is_active: bool


class SupplierResponse(BaseModel):
    id: UUID
    organization_id: UUID
    supplier_kind: SupplierKind
    display_name: str
    commercial_status: SupplierCommercialStatus
    source: SupplierSource
    assigned_owner_user_id: UUID | None
    created_by_user_id: UUID
    is_active: bool
    version: int
    tags: list[SupplierTagResponse] = Field(default_factory=list)


class SupplierRepresentativeCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    is_primary: bool = False

    @field_validator("display_name", "job_title")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if re.fullmatch(r"[+0-9() .-]{3,32}", normalized) is None:
            raise ValueError("Phone contains invalid characters.")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized) is None:
            raise ValueError("Email format is invalid.")
        return normalized


class SupplierRepresentativeUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=254)
    is_primary: bool | None = None
    is_active: bool | None = None

    @field_validator("display_name", "job_title")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if re.fullmatch(r"[+0-9() .-]{3,32}", normalized) is None:
            raise ValueError("Phone contains invalid characters.")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized) is None:
            raise ValueError("Email format is invalid.")
        return normalized

    @model_validator(mode="after")
    def reject_non_nullable_nulls(self) -> "SupplierRepresentativeUpdateRequest":
        for field_name in ("display_name", "is_primary", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self


class SupplierRepresentativeResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    display_name: str
    job_title: str | None
    phone: str | None
    email: str | None
    contact_masked: bool
    is_primary: bool
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class SupplierNoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Note body cannot be empty.")
        return normalized


class SupplierNoteUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Note body cannot be empty.")
        return normalized


class SupplierNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    author_user_id: UUID
    body: str
    version: int
    created_at: datetime
    updated_at: datetime


def normalize_external_id(value: str) -> str:
    # External IDs are opaque and may be case-sensitive. Normalize Unicode form
    # and surrounding whitespace only; do not case-fold or rewrite punctuation.
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ValueError("External ID cannot be empty.")
    if len(normalized) > 128:
        raise ValueError("External ID is too long.")
    if any(unicodedata.category(char).startswith("C") for char in normalized):
        raise ValueError("External ID contains control characters.")
    return normalized


class SupplierExternalReferenceCreateRequest(BaseModel):
    system: SupplierExternalSystem
    external_id: str = Field(min_length=1, max_length=128)

    @field_validator("external_id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return normalize_external_id(value)


class SupplierExternalReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    supplier_id: UUID
    organization_id: UUID
    system: SupplierExternalSystem
    external_id: str
    created_by_user_id: UUID
    created_at: datetime
