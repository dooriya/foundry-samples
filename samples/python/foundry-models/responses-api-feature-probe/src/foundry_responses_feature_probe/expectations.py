# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from typing import Any

from foundry_responses_feature_probe.models import (
    EXPECTED_UNKNOWN,
    ExpectationSet,
    ExpectationsSource,
    Status,
)

EXPECTATIONS_SCHEMA_VERSION = "1.0"
_ALLOWED_EXPECTATIONS = {status.value for status in Status} | {EXPECTED_UNKNOWN}


class ExpectationsError(ValueError):
    """A local expectations document is invalid."""


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExpectationsError(f"Expectations field '{field_name}' must be a non-empty string.")
    return value.strip()


def load_expectations(path: Path | None) -> ExpectationSet:
    """Load a versioned local expectations document without treating it as authoritative."""

    if path is None:
        return ExpectationSet()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExpectationsError("Unable to read the local expectations JSON file.") from exc

    if not isinstance(document, dict):
        raise ExpectationsError("The expectations document must be a JSON object.")
    if set(document) != {"schemaVersion", "source", "expectations"}:
        raise ExpectationsError("The expectations document contains unknown or missing fields.")
    if document.get("schemaVersion") != EXPECTATIONS_SCHEMA_VERSION:
        raise ExpectationsError(
            f"Expectations schemaVersion must be '{EXPECTATIONS_SCHEMA_VERSION}'."
        )

    source_value = document.get("source")
    if not isinstance(source_value, dict):
        raise ExpectationsError("Expectations field 'source' must be an object.")
    if set(source_value) != {"name", "version"}:
        raise ExpectationsError("Expectations field 'source' contains unknown or missing fields.")
    source = ExpectationsSource(
        name=_required_string(source_value.get("name"), "source.name"),
        version=_required_string(source_value.get("version"), "source.version"),
    )

    raw_expectations = document.get("expectations")
    if not isinstance(raw_expectations, dict):
        raise ExpectationsError("Expectations field 'expectations' must be an object.")

    statuses: dict[str, str] = {}
    for capability_id, value in raw_expectations.items():
        if not isinstance(capability_id, str) or not capability_id or not isinstance(value, dict):
            raise ExpectationsError("Each expectation must map a capability ID to an object.")
        if set(value) != {"status"}:
            raise ExpectationsError(
                f"Expectation '{capability_id}' contains unknown or missing fields."
            )
        status = value.get("status")
        if status not in _ALLOWED_EXPECTATIONS:
            allowed = ", ".join(sorted(_ALLOWED_EXPECTATIONS))
            raise ExpectationsError(
                f"Expectation '{capability_id}' has an invalid status; expected one of: {allowed}."
            )
        statuses[capability_id] = status

    return ExpectationSet(source=source, statuses=statuses)
