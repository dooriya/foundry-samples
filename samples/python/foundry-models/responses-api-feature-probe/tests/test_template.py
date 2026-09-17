# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_azure_yaml_declares_byo_feature_probe_template() -> None:
    template_root = Path(__file__).parents[1]
    document = yaml.safe_load((template_root / "azure.yaml").read_text(encoding="utf-8"))

    assert document == {
        "name": "foundry-responses-feature-probe",
        "metadata": {
            "template": "foundry-samples/foundry-responses-feature-probe@0.1.0",
        },
    }


def test_sample_yaml_declares_offline_repository_validation() -> None:
    template_root = Path(__file__).parents[1]
    document = yaml.safe_load((template_root / "sample.yaml").read_text(encoding="utf-8"))

    assert document == {
        "name": "Responses API Feature Probe",
        "description": (
            "Offline-validated Python probe for observed Microsoft Foundry Responses API "
            "capabilities."
        ),
        "build": 'python -m pip install --disable-pip-version-check ".[dev]"',
        "validate": "python -m ruff check . && python -m ruff format --check .",
        "test": "python -m pytest -q",
    }


def test_example_expectations_match_versioned_schema() -> None:
    template_root = Path(__file__).parents[1]
    schema = _load_json(template_root / "schemas" / "expectations.v1.json")
    document = _load_json(template_root / "expectations.example.json")

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)
