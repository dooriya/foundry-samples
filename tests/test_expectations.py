# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path

import pytest

from foundry_responses_feature_probe.expectations import ExpectationsError, load_expectations


def test_no_expectations_defaults_to_unknown() -> None:
    expectations = load_expectations(None)

    assert expectations.source is None
    assert expectations.status_for("basic_response") == "unknown"


def test_load_versioned_expectations(tmp_path: Path) -> None:
    path = tmp_path / "expectations.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "source": {"name": "platform-snapshot", "version": "42"},
                "expectations": {
                    "basic_response": {"status": "pass"},
                    "reasoning_effort": {"status": "unsupported"},
                },
            }
        ),
        encoding="utf-8",
    )

    expectations = load_expectations(path)

    assert expectations.source is not None
    assert expectations.source.name == "platform-snapshot"
    assert expectations.status_for("basic_response") == "pass"
    assert expectations.status_for("streaming_response") == "unknown"


def test_rejects_unknown_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "expectations.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "2.0",
                "source": {"name": "future", "version": "1"},
                "expectations": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ExpectationsError, match="schemaVersion"):
        load_expectations(path)


def test_rejects_unknown_expectation_fields(tmp_path: Path) -> None:
    path = tmp_path / "expectations.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "source": {"name": "local", "version": "1"},
                "expectations": {
                    "basic_response": {"status": "pass", "prompt": "must not be accepted"}
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ExpectationsError, match="unknown or missing"):
        load_expectations(path)
