# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import sys
from pathlib import Path

from foundry_responses_feature_probe.client import live_responses_client
from foundry_responses_feature_probe.config import ConfigurationError, load_config
from foundry_responses_feature_probe.expectations import ExpectationsError, load_expectations
from foundry_responses_feature_probe.models import (
    EXPECTED_UNKNOWN,
    ResultsManifest,
    Status,
    TargetMetadata,
)
from foundry_responses_feature_probe.redaction import sanitize_text
from foundry_responses_feature_probe.reporting import write_reports
from foundry_responses_feature_probe.runner import run_diagnostics
from foundry_responses_feature_probe.scenarios import ALL_SCENARIOS, SCENARIO_IDS
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Observe Responses API capabilities on an existing Microsoft Foundry deployment."
        )
    )
    parser.add_argument(
        "--environment",
        help="Read missing settings from this azd environment instead of the selected environment.",
    )
    parser.add_argument(
        "--expectations",
        type=Path,
        help="Optional local versioned expectations JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Report destination (default: reports).",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=SCENARIO_IDS,
        help="Run only this capability ID; repeat to select multiple scenarios.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=90.0,
        help="Per-request timeout in seconds (default: 90).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="OpenAI SDK retry count (default: 1).",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List capability IDs without making requests.",
    )
    return parser


def _exit_code(manifest: ResultsManifest) -> int:
    if any(result.status is Status.FAIL for result in manifest.scenarios):
        return 1
    if any(
        result.expected != EXPECTED_UNKNOWN and result.expected != result.status.value
        for result in manifest.scenarios
    ):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_scenarios:
        for scenario in ALL_SCENARIOS:
            print(f"{scenario.capability_id}: {scenario.name}")
        return 0

    try:
        expectations = load_expectations(args.expectations)
        config = load_config(
            environment_name=args.environment,
            request_timeout_seconds=args.request_timeout,
            max_retries=args.max_retries,
        )
    except (ConfigurationError, ExpectationsError) as error:
        print(f"error: {sanitize_text(str(error))}", file=sys.stderr)
        return 2

    target = TargetMetadata(
        endpoint=config.endpoint,
        model=config.model,
        token_scope=config.token_scope,
        request_timeout_seconds=config.request_timeout_seconds,
        max_retries=config.max_retries,
    )
    try:
        with live_responses_client(config) as client:
            manifest = run_diagnostics(
                context=ScenarioContext(client=client, model=config.model),
                target=target,
                scenarios=ALL_SCENARIOS,
                expectations=expectations,
                selected_capability_ids=args.scenario,
            )
    except Exception as error:
        print(
            f"error: unable to initialize or close the API client: {sanitize_text(str(error))}",
            file=sys.stderr,
        )
        return 2

    try:
        json_path, markdown_path = write_reports(manifest, args.output_dir)
    except OSError as error:
        print(f"error: unable to write reports: {sanitize_text(str(error))}", file=sys.stderr)
        return 2

    print(f"JSON report: {sanitize_text(str(json_path))}")
    print(f"Markdown report: {sanitize_text(str(markdown_path))}")
    return _exit_code(manifest)
