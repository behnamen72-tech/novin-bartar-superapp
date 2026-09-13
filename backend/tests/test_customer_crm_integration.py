from datetime import datetime, timezone

import httpx
import jwt
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.modules.customers.integration import (
    CommerceIntegrationUnavailableError,
    _base_url,
    _retry_delay_seconds,
    create_commerce_service_token,
)


def test_commerce_service_token_has_dedicated_short_lived_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "commerce-test-secret-0123456789abcdef"
    monkeypatch.setattr(settings, "commerce_integration_jwt_secret", SecretStr(secret))
    monkeypatch.setattr(settings, "commerce_integration_jwt_issuer", "super-app-test")
    monkeypatch.setattr(settings, "commerce_integration_jwt_audience", "virtual-store-test")
    monkeypatch.setattr(settings, "commerce_integration_service_subject", "super-app-service")
    monkeypatch.setattr(settings, "commerce_integration_token_ttl_seconds", 120)

    token = create_commerce_service_token(scope="customer.reference.validate")
    claims = jwt.decode(
        token,
        secret,
        algorithms=[settings.commerce_integration_jwt_algorithm],
        issuer="super-app-test",
        audience="virtual-store-test",
    )

    assert claims["sub"] == "super-app-service"
    assert claims["scope"] == "customer.reference.validate"
    assert claims["jti"]
    assert 0 < claims["exp"] - claims["iat"] <= 120
    assert claims["iat"] <= int(datetime.now(timezone.utc).timestamp())


def test_commerce_base_url_requires_https_outside_local_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "commerce_integration_base_url", "http://commerce.internal")
    with pytest.raises(CommerceIntegrationUnavailableError):
        _base_url()

    monkeypatch.setattr(settings, "commerce_integration_base_url", "https://commerce.internal/")
    assert _base_url() == "https://commerce.internal"


def test_retry_after_is_honored_but_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "commerce_integration_retry_backoff_seconds", 0.1)
    monkeypatch.setattr(settings, "commerce_integration_timeout_seconds", 3.0)

    response = httpx.Response(429, headers={"Retry-After": "999"})
    assert _retry_delay_seconds(response, attempt=1) == 3.0

    malformed = httpx.Response(429, headers={"Retry-After": "not-a-number"})
    assert _retry_delay_seconds(malformed, attempt=2) == pytest.approx(0.2)
