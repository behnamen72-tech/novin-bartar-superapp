from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class UserListItem(BaseModel):
    id: UUID
    person_id: UUID
    person_name: str
    email: str
    username: str | None
    is_active: bool
    last_login_at: datetime | None
    organization_names: list[str]


class UserCreateRequest(BaseModel):
    person_id: UUID
    email: str = Field(min_length=3, max_length=320)
    username: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("A valid email-like login is required.")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if "@" in normalized:
            raise ValueError("Username cannot contain @ because @-identifiers are email logins.")
        return normalized or None


class UserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    username: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValueError("A valid email-like login is required.")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_optional_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if "@" in normalized:
            raise ValueError("Username cannot contain @ because @-identifiers are email logins.")
        return normalized or None

    @model_validator(mode="after")
    def reject_null_email(self) -> "UserUpdateRequest":
        if "email" in self.model_fields_set and self.email is None:
            raise ValueError("email cannot be null.")
        return self


class UserStatusRequest(BaseModel):
    is_active: bool


class UserPasswordResetRequest(BaseModel):
    new_password: SecretStr = Field(min_length=12, max_length=256)
