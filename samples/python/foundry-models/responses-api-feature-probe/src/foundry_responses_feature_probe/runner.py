# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Collection, Sequence
from datetime import UTC, datetime
from time import perf_counter

from foundry_responses_feature_probe.api_errors import (
    classify_api_error,
    sanitized_error_details,
)
from foundry_responses_feature_probe.models import (
    ExpectationSet,
    ResultsManifest,
    ScenarioObservation,
    ScenarioResult,
    Status,
    TargetMetadata,
)
from foundry_responses_feature_probe.scenarios.base import Scenario, ScenarioContext


def run_diagnostics(
    *,
    context: ScenarioContext,
    target: TargetMetadata,
    scenarios: Sequence[Scenario],
    expectations: ExpectationSet,
    selected_capability_ids: Collection[str] | None = None,
) -> ResultsManifest:
    """Run isolated scenarios and retain a result even when one request fails."""

    tested_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    run_started = perf_counter()
    selected = set(selected_capability_ids) if selected_capability_ids else None
    results: list[ScenarioResult] = []

    for scenario in scenarios:
        expected = expectations.status_for(scenario.capability_id)
        if selected is not None and scenario.capability_id not in selected:
            results.append(
                ScenarioResult(
                    capability_id=scenario.capability_id,
                    name=scenario.name,
                    status=Status.SKIPPED,
                    expected=expected,
                    observed={"reason": "not_selected"},
                    duration_ms=0,
                )
            )
            continue

        scenario_started = perf_counter()
        try:
            observation = scenario.run(context)
        except Exception as error:
            observation = ScenarioObservation(
                status=classify_api_error(error),
                evidence={"requestCompleted": False},
                error=sanitized_error_details(error),
            )
        duration_ms = round((perf_counter() - scenario_started) * 1000)
        results.append(
            ScenarioResult(
                capability_id=scenario.capability_id,
                name=scenario.name,
                status=observation.status,
                expected=expected,
                observed=observation.evidence,
                duration_ms=duration_ms,
                error=observation.error,
            )
        )

    return ResultsManifest(
        target=target,
        tested_at=tested_at,
        duration_ms=round((perf_counter() - run_started) * 1000),
        scenarios=tuple(results),
        expectations_source=expectations.source,
    )
