# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from foundry_responses_feature_probe.models import (
    ExpectationSet,
    ExpectationsSource,
    ScenarioObservation,
    Status,
    TargetMetadata,
)
from foundry_responses_feature_probe.reporting import _display_result, write_reports
from foundry_responses_feature_probe.runner import run_diagnostics
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


class PassingScenario:
    capability_id = "basic_response"
    name = "Basic response"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        assert context.model == "deployment"
        return ScenarioObservation(Status.PASS, {"outputTextPresent": True})


class FailingScenario:
    capability_id = "failure"
    name = "Failure"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        raise RuntimeError(
            "Authorization: Bearer secret-token "
            "https://user:password@example.test/path?sig=query-secret"
        )


def target() -> TargetMetadata:
    return TargetMetadata(
        endpoint="https://example.services.ai.azure.com/openai/v1/",
        model="deployment",
        token_scope="https://ai.azure.com/.default",
        request_timeout_seconds=90,
        max_retries=1,
    )


def test_runner_attaches_unknown_default_expectation_and_skipped_results() -> None:
    manifest = run_diagnostics(
        context=ScenarioContext(client=SimpleNamespace(), model="deployment"),
        target=target(),
        scenarios=(PassingScenario(), FailingScenario()),
        expectations=ExpectationSet(),
        selected_capability_ids={"basic_response"},
    )

    assert manifest.scenarios[0].status is Status.PASS
    assert manifest.scenarios[0].expected == "unknown"
    assert manifest.scenarios[1].status is Status.SKIPPED
    assert manifest.scenarios[1].observed == {"reason": "not_selected"}


@pytest.mark.parametrize(
    ("status", "display"),
    [
        ("pass", "Supported"),
        ("fail", "Failed validation"),
        ("unsupported", "Unsupported"),
        ("not_applicable", "Not applicable"),
        ("skipped", "Not tested"),
        ("inconclusive", "Inconclusive"),
    ],
)
def test_display_result_uses_capability_language(status: str, display: str) -> None:
    assert _display_result(status) == display


def test_report_matches_schema_and_contains_no_sensitive_error(tmp_path: Path) -> None:
    manifest = run_diagnostics(
        context=ScenarioContext(client=SimpleNamespace(), model="deployment"),
        target=target(),
        scenarios=(PassingScenario(), FailingScenario()),
        expectations=ExpectationSet(
            source=ExpectationsSource(name="local", version="1"),
            statuses={"basic_response": "pass"},
        ),
    )

    json_path, markdown_path = write_reports(manifest, tmp_path)
    document = json.loads(json_path.read_text(encoding="utf-8"))
    template_root = Path(__file__).parents[1]
    schema = json.loads(
        (template_root / "schemas" / "results-manifest.v1.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)

    assert document["reportType"] == "observed_capability_diagnostics"
    assert document["scenarios"][0]["expectationMatched"] is True
    assert document["scenarios"][1]["status"] == "fail"
    combined = json_path.read_text(encoding="utf-8") + markdown_path.read_text(encoding="utf-8")
    for secret in ("secret-token", "user:password", "query-secret", "sig="):
        assert secret not in combined
    assert "not an authoritative Microsoft feature-parity certification" in combined
    assert "`local@1` (local file)" in combined
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "| Capability | Result | Duration |" in markdown
    assert "| `basic_response` | Supported |" in markdown
    assert "| `failure` | Failed validation |" in markdown
    assert "Expected | Match" not in markdown
    assert "- Expected result: **Supported**" in markdown
    assert "- Matches expectation: **yes**" in markdown
    assert "- Expected result: **unknown**" not in markdown
