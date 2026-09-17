# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from foundry_responses_feature_probe.api_errors import (
    classify_api_error,
    sanitized_error_details,
)
from foundry_responses_feature_probe.helpers import cached_tokens
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext

_PREFIX_UNIT = (
    "Stable diagnostic context about a fictional observatory, its instruments, "
    "calibration schedule, weather records, and harmless maintenance procedures. "
)
_STABLE_PREFIX = _PREFIX_UNIT * 100


class PromptCacheScenario:
    capability_id = "prompt_cache_reporting"
    name = "Prompt-cache reporting"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        request = {
            "model": context.model,
            "max_output_tokens": 16,
        }
        try:
            context.client.responses.create(
                **request,
                input=f"{_STABLE_PREFIX}\nRun A: reply with the letter A.",
            )
            second = context.client.responses.create(
                **request,
                input=f"{_STABLE_PREFIX}\nRun B: reply with the letter B.",
            )
        except Exception as error:
            status = classify_api_error(error, ("cache", "cached", "prompt"))
            return ScenarioObservation(
                status=status,
                evidence={
                    "outcome": (
                        "explicitly_rejected"
                        if status is Status.UNSUPPORTED
                        else "requests_not_completed"
                    ),
                    "stablePrefixCharacters": len(_STABLE_PREFIX),
                    "stablePrefixWords": len(_STABLE_PREFIX.split()),
                },
                error=sanitized_error_details(error),
            )

        details_present, count = cached_tokens(second)
        evidence = {
            "requestsCompleted": 2,
            "stablePrefixCharacters": len(_STABLE_PREFIX),
            "stablePrefixWords": len(_STABLE_PREFIX.split()),
            "cachedTokenMetricPresent": details_present,
            "cachedTokens": count,
        }
        if details_present and isinstance(count, int) and count > 0:
            evidence["outcome"] = "cached_tokens_observed"
            return ScenarioObservation(status=Status.PASS, evidence=evidence)
        if details_present and isinstance(count, int) and count < 0:
            evidence["outcome"] = "invalid_cached_token_metric"
            return ScenarioObservation(status=Status.FAIL, evidence=evidence)

        evidence["outcome"] = (
            "cached_token_metric_zero" if details_present and count == 0 else "metric_unavailable"
        )
        return ScenarioObservation(status=Status.INCONCLUSIVE, evidence=evidence)
