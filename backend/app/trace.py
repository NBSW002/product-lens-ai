from collections.abc import Mapping, Sequence
from typing import Any


SENSITIVE_KEYS = ("api_key", "authorization", "token", "secret", "password")
MAX_TEXT_LENGTH = 2000
MAX_LIST_ITEMS = 25


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(term in normalized for term in SENSITIVE_KEYS)


def sanitize_trace_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive(str(key)) else sanitize_trace_value(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_trace_value(item) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
        return value[:MAX_TEXT_LENGTH] + "…[TRUNCATED]"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)

