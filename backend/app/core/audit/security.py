from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import SecretStr

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
    "apikey",
    "jwt",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def sanitize_audit_value(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return _REDACTED

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, SecretStr):
        return _REDACTED

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Enum):
        return sanitize_audit_value(value.value)

    if isinstance(value, dict):
        return {
            str(item_key): sanitize_audit_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [sanitize_audit_value(item) for item in value]

    return str(value)


def sanitize_audit_payload(
    payload: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if payload is None:
        return None
    sanitized = sanitize_audit_value(dict(payload))
    if not isinstance(sanitized, dict):
        raise TypeError("Audit payload must sanitize to a dictionary.")
    return sanitized
