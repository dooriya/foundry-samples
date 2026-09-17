# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_AUTH_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)([^\s,;]+)")
_SECRET_PATTERN = re.compile(
    r"(?i)((?:api[-_ ]?key|x-api-key|subscription[-_ ]?key|"
    r"access[-_ ]?token|refresh[-_ ]?token|token|client[-_ ]?secret|sig)"
    r"\s*[:=]\s*)([^\s,;]+)"
)


def sanitize_url(value: str) -> str:
    """Remove URL user information, query strings, and fragments."""

    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if not parts.scheme or not host:
            return "[REDACTED_URL]"
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        try:
            port = f":{parts.port}" if parts.port is not None else ""
        except ValueError:
            port = ""
        return urlunsplit((parts.scheme, f"{host}{port}", parts.path, "", ""))
    except ValueError:
        return "[REDACTED_URL]"


def _sanitize_url_match(match: re.Match[str]) -> str:
    candidate = match.group(0)
    trailing = ""
    while candidate and candidate[-1] in ".,;)]}":
        trailing = candidate[-1] + trailing
        candidate = candidate[:-1]
    return sanitize_url(candidate) + trailing


def sanitize_text(value: str) -> str:
    """Redact common credentials and credential-bearing URLs from text."""

    sanitized = _URL_PATTERN.sub(_sanitize_url_match, value)
    sanitized = _AUTH_PATTERN.sub(r"\1[REDACTED]", sanitized)
    return _SECRET_PATTERN.sub(r"\1[REDACTED]", sanitized)


def sanitize_value(value: Any) -> Any:
    """Recursively sanitize strings before report serialization."""

    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(key): sanitize_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [sanitize_value(item) for item in value]
    return value
