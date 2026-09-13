from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PersonRelationshipItem(BaseModel):
    id: UUID
    organization_id: UUID
    organization_name: str
    relationship_code: str
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool


class PersonListItem(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    is_active: bool
    relationships: list[PersonRelationshipItem]


class PersonCreateRequest(BaseModel):
    organization_id: UUID
    relationship_code: str = Field(min_length=1, max_length=80)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("first_name", "last_name", "relationship_code")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be empty.")
        return normalized

    @field_validator("email", "phone")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_dates(self) -> "PersonCreateRequest":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("Relationship end_date cannot be before start_date.")
        return self


class PersonUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Value cannot be empty.")
        return normalized

    @field_validator("email", "phone")
    @classmethod
    def normalize_optional_contact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PersonStatusRequest(BaseModel):
    is_active: bool


class PersonRelationshipCreateRequest(BaseModel):
    organization_id: UUID
    relationship_code: str = Field(min_length=1, max_length=80)
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("relationship_code")
    @classmethod
    def normalize_relationship_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Relationship code cannot be empty.")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> "PersonRelationshipCreateRequest":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("Relationship end_date cannot be before start_date.")
        return self


class PersonRelationshipStatusRequest(BaseModel):
    is_active: bool
