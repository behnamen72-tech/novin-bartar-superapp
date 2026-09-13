from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import sleep
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
import jwt

from app.core.config import settings
from app.modules.customers.schemas import (
    CommerceActivityProjection,
    CommerceCustomerValidationResult,
)


class CommerceIntegrationUnavailableError(RuntimeError):
    pass


class CommerceIntegrationProtocolError(RuntimeError):
    pass


def create_commerce_service_token(*, scope: str) -> str:
    secret = settings.commerce_integration_jwt_secret
    if secret is None:
        raise CommerceIntegrationUnavailableError(
            "Commerce integration service credentials are not configured."
        )
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=settings.commerce_integration_token_ttl_seconds)
    payload = {
        "sub": settings.commerce_integration_service_subject,
        "iss": settings.commerce_integration_jwt_issuer,
        "aud": settings.commerce_integration_jwt_audience,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": str(uuid4()),
    }
    return jwt.encode(
        payload,
        secret.get_secret_value(),
        algorithm=settings.commerce_integration_jwt_algorithm,
    )


def _base_url() -> str:
    value = settings.commerce_integration_base_url
    if not value:
        raise CommerceIntegrationUnavailableError(
            "Commerce integration base URL is not configured."
        )
    normalized = value.rstrip("/")
    if not normalized.startswith("https://"):
        local_allowed = settings.app_env.lower() in {"development", "test"} and (
            normalized.startswith("http://localhost")
            or normalized.startswith("http://127.0.0.1")
        )
        if not local_allowed:
            raise CommerceIntegrationUnavailableError(
                "Commerce integration requires HTTPS outside local development."
            )
    return normalized



def _retry_delay_seconds(response: httpx.Response | None, *, attempt: int) -> float:
    base_delay = settings.commerce_integration_retry_backoff_seconds * attempt
    if response is None or response.status_code != 429:
        return base_delay
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return base_delay
    try:
        requested = max(0.0, float(retry_after))
    except ValueError:
        return base_delay
    # Honor numeric Retry-After without allowing an internal dependency to stall
    # a CRM request beyond the already bounded integration timeout policy.
    return max(base_delay, min(requested, settings.commerce_integration_timeout_seconds))


def _get_json(path: str, *, scope: str, params: dict[str, str] | None = None) -> object:
    token = create_commerce_service_token(scope=scope)
    attempts = settings.commerce_integration_max_attempts
    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(
                base_url=_base_url(),
                timeout=settings.commerce_integration_timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = client.get(
                    path,
                    params=params,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError) as exc:
            if attempt < attempts:
                sleep(_retry_delay_seconds(None, attempt=attempt))
                continue
            raise CommerceIntegrationUnavailableError(
                "Commerce integration is temporarily unavailable."
            ) from exc

        if response.status_code in {429, 500, 502, 503, 504}:
            if attempt < attempts:
                sleep(_retry_delay_seconds(response, attempt=attempt))
                continue
            raise CommerceIntegrationUnavailableError(
                "Commerce integration is temporarily unavailable."
            )
        if response.status_code in {401, 403}:
            raise CommerceIntegrationUnavailableError(
                "Commerce integration service authentication failed."
            )
        if 300 <= response.status_code < 400:
            raise CommerceIntegrationProtocolError(
                "Commerce integration redirects are not accepted."
            )
        if response.status_code >= 400:
            raise CommerceIntegrationProtocolError(
                f"Commerce integration rejected the request with status {response.status_code}."
            )
        try:
            return response.json()
        except ValueError as exc:
            raise CommerceIntegrationProtocolError(
                "Commerce integration returned malformed JSON."
            ) from exc

    raise CommerceIntegrationUnavailableError("Commerce integration is temporarily unavailable.")


def validate_commerce_customer_reference(
    commerce_customer_ref: str,
    *,
    organization_id: UUID,
) -> CommerceCustomerValidationResult:
    payload = _get_json(
        f"/internal/integration/v1/customers/{quote(commerce_customer_ref, safe='')}/validation",
        scope="customer.reference.validate",
        params={"organization_id": str(organization_id)},
    )
    try:
        return CommerceCustomerValidationResult.model_validate(payload)
    except Exception as exc:
        raise CommerceIntegrationProtocolError(
            "Commerce customer validation response did not match the contract."
        ) from exc


def fetch_commerce_customer_activity(
    commerce_customer_ref: str,
    *,
    organization_id: UUID,
) -> CommerceActivityProjection:
    payload = _get_json(
        f"/internal/integration/v1/customers/{quote(commerce_customer_ref, safe='')}/activity",
        scope="customer.activity.read",
        params={"organization_id": str(organization_id), "limit": "10"},
    )
    try:
        return CommerceActivityProjection.model_validate(payload)
    except Exception as exc:
        raise CommerceIntegrationProtocolError(
            "Commerce activity response did not match the contract."
        ) from exc
