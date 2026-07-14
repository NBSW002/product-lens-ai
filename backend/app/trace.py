from collections.abc import Mapping, Sequence
import re
from typing import Any


SENSITIVE_KEYS = ("api_key", "authorization", "token", "secret", "password", "credential", "signature")
MAX_TEXT_LENGTH = 2000
MAX_LIST_ITEMS = 25


def sanitize_error(message: str) -> str:
    cleaned = re.sub(
        r"(?i)(?:api[_-]?key|authorization|token|secret|password|credential|signature)\s*[:=]\s*(?:bearer\s+)?[^&\s]+",
        "[REDACTED]",
        message,
    )
    cleaned = re.sub(r"(?i)bearer\s+[a-z0-9._~+/-]{8,}", "Bearer [REDACTED]", cleaned)
    cleaned = re.sub(r"(?i)\b(?:sk-[a-z0-9_-]{8,}|gh[oprsu]_[a-z0-9_-]{8,}|[a-f0-9]{32})\b", "[REDACTED]", cleaned)
    return cleaned[:MAX_TEXT_LENGTH]


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
