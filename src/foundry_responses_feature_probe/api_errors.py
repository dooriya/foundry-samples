# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Iterable
from typing import Any

from foundry_responses_feature_probe.models import Status
from foundry_responses_feature_probe.redaction import sanitize_text

_UNSUPPORTED_MARKERS = (
    "not supported",
    "does not support",
    "unsupported",
    "unknown parameter",
    "unrecognized parameter",
)


def sanitized_error_details(error: Exception) -> dict[str, Any]:
    """Extract a bounded, credential-safe subset of an API exception."""

    message = getattr(error, "message", None)
    if not isinstance(message, str):
        message = str(error)

    details: dict[str, Any] = {
        "type": type(error).__name__,
        "message": sanitize_text(message),
    }
    for source_name, report_name in (
        ("status_code", "statusCode"),
        ("code", "code"),
        ("param", "param"),
        ("request_id", "requestId"),
    ):
        value = getattr(error, source_name, None)
        if isinstance(value, int | str) and value != "":
            details[report_name] = sanitize_text(value) if isinstance(value, str) else value
    return details


def classify_api_error(error: Exception, feature_terms: Iterable[str] = ()) -> Status:
    """Classify explicit feature rejection separately from transient or request failures."""

    details = sanitized_error_details(error)
    message = str(details.get("message", "")).lower()
    parameter = str(details.get("param", "")).lower()
    status_code = details.get("statusCode")
    terms = tuple(term.lower() for term in feature_terms)

    explicit_rejection = any(marker in message for marker in _UNSUPPORTED_MARKERS)
    feature_identified = not terms or any(term in message or term in parameter for term in terms)
    if status_code in {400, 404, 422} and explicit_rejection and feature_identified:
        return Status.UNSUPPORTED
    if status_code in {400, 422} and parameter and any(term in parameter for term in terms):
        return Status.UNSUPPORTED
    if status_code in {408, 409, 425, 429} or (isinstance(status_code, int) and status_code >= 500):
        return Status.INCONCLUSIVE
    if status_code is None and any(
        marker in type(error).__name__.lower() for marker in ("connection", "timeout")
    ):
        return Status.INCONCLUSIVE
    return Status.FAIL
