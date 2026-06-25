from copy import deepcopy
from typing import Any


REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {
    "authorization",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "set-cookie",
    "api_key",
    "apikey",
    "secret",
}


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if str(key).lower() in SENSITIVE_KEYS
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return deepcopy(value)
