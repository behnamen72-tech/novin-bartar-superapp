from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.documents.models import (
    DocumentLinkEntityType,
    DocumentPermissionType,
    DocumentPriority,
    DocumentStatus,
    RetentionBasis,
)


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    document_type: str = Field(min_length=1, max_length=100)
    organization_id: UUID

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Document title cannot be empty.")
        return normalized

    @field_validator("document_type")
    @classmethod
    def normalize_document_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Document type cannot be empty.")
        return normalized


class DocumentMetadataUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    document_type: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    priority: DocumentPriority | None = None
    category_id: UUID | None = None
    expires_at: datetime | None = None
    retention_policy_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def normalize_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Document title cannot be empty.")
        return normalized

    @field_validator("document_type")
    @classmethod
    def normalize_optional_document_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Document type cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("expires_at")
    @classmethod
    def require_expiration_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Expiration date must include a timezone offset.")
        return value


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    document_type: str
    description: str | None
    priority: DocumentPriority
    status: DocumentStatus
    organization_id: UUID
    created_by: UUID
    category_id: UUID | None
    expires_at: datetime | None
    retention_policy_id: UUID | None
    retention_review_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    file_name: str
    mime_type: str
    created_by: UUID
    created_at: datetime
    size_bytes: int
    checksum: str | None


class DocumentLinkCreateRequest(BaseModel):
    entity_type: DocumentLinkEntityType
    entity_id: UUID


class DocumentLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    entity_type: DocumentLinkEntityType
    entity_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentPermissionCreateRequest(BaseModel):
    role_id: UUID
    permission_type: DocumentPermissionType


class DocumentPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    role_id: UUID
    permission_type: DocumentPermissionType
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    versions: list[DocumentVersionResponse]
    links: list[DocumentLinkResponse]


class DocumentCategoryCreateRequest(BaseModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    parent_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Category name cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_category_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DocumentCategoryUpdateRequest(BaseModel):
    code: str | None = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    parent_id: UUID | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_code(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Category name cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_optional_category_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DocumentCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    parent_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RetentionPolicyCreateRequest(BaseModel):
    organization_id: UUID
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    retention_days: int = Field(ge=1, le=36500)
    basis: RetentionBasis

    @field_validator("code")
    @classmethod
    def normalize_retention_code(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def normalize_retention_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Retention policy name cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_retention_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RetentionPolicyUpdateRequest(BaseModel):
    code: str | None = Field(default=None, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    name: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    retention_days: int | None = Field(default=None, ge=1, le=36500)
    basis: RetentionBasis | None = None

    @field_validator("code")
    @classmethod
    def normalize_optional_retention_code(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @field_validator("name")
    @classmethod
    def normalize_optional_retention_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Retention policy name cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_optional_retention_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RetentionPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    retention_days: int
    basis: RetentionBasis
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentExpirationState(str, Enum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


class DocumentExpirationResponse(BaseModel):
    document: DocumentResponse
    expiration_state: DocumentExpirationState
    days_remaining: int


class DocumentRetentionDueResponse(BaseModel):
    document: DocumentResponse
    days_overdue: int


class DocumentTimelineEventResponse(BaseModel):
    id: UUID
    action: str
    actor_identifier: str | None
    occurred_at: datetime
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    event_metadata: dict[str, object] | None
