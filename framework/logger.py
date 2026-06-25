import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "logs" / "automation.log"
REDACTED = "***REDACTED***"
SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
}


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if any(getattr(handler, "_api_framework_handler", False) for handler in root_logger.handlers):
        return

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler._api_framework_handler = True  # type: ignore[attr-defined]
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)


def redact(value: Any, key: str = "") -> Any:
    if key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, dict):
        return {item_key: redact(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    safe_query = urlencode(
        [
            (key, REDACTED if key.lower() in SENSITIVE_KEYS else value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, safe_query, parts.fragment))


def to_log_text(value: Any) -> str:
    safe_value = redact(value)
    try:
        return json.dumps(safe_value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return repr(safe_value)

