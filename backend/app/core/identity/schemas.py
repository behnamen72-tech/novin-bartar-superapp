from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(ge=1)
    refresh_token: str
    refresh_expires_in: int = Field(ge=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: SecretStr


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_id: UUID
    email: str
    username: str | None
    is_active: bool
