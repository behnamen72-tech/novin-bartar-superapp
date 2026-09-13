from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Novin Bartar Super App"
    app_env: str = "development"
    database_url: str

    # Environment format:
    # CORS_ALLOWED_ORIGINS=http://localhost:3000,https://example.com
    cors_allowed_origins: str = "http://localhost:3000"

    # Authentication
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    auth_refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    jwt_issuer: str = "novin-bartar-superapp"
    jwt_audience: str = "novin-bartar-superapp-api"

    # Commerce integration (D2 CRM -> Virtual Store; never browser/user auth)
    commerce_integration_base_url: str | None = None
    commerce_integration_jwt_secret: SecretStr | None = None
    commerce_integration_jwt_algorithm: Literal["HS256"] = "HS256"
    commerce_integration_jwt_issuer: str = "novin-bartar-superapp"
    commerce_integration_jwt_audience: str = "virtual_store.integration"
    commerce_integration_service_subject: str = "super_app"
    commerce_integration_token_ttl_seconds: int = Field(default=300, ge=30, le=300)
    commerce_integration_timeout_seconds: float = Field(default=3.0, gt=0, le=15)
    commerce_integration_max_attempts: int = Field(default=2, ge=1, le=3)
    commerce_integration_retry_backoff_seconds: float = Field(default=0.1, ge=0, le=1)

    # Documents Core
    documents_storage_root: str = "storage/documents"
    documents_max_file_size_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=1,
        le=500 * 1024 * 1024,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("jwt_secret_key")
    @classmethod
    def reject_example_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if secret.startswith("replace-with-"):
            raise ValueError(
                "JWT_SECRET_KEY must be replaced with a cryptographically random secret."
            )
        return value

    @field_validator("commerce_integration_jwt_secret")
    @classmethod
    def reject_example_commerce_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value()
        if len(secret) < 32 or secret.startswith("replace-with-"):
            raise ValueError(
                "COMMERCE_INTEGRATION_JWT_SECRET must be a dedicated random secret of at least 32 characters."
            )
        return value

    @property
    def cors_allowed_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
