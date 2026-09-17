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
_MAX_REQUESTS = 4
_CACHEABLE_INPUT = f"{_STABLE_PREFIX}\nReply with the single letter A."


class PromptCacheScenario:
    capability_id = "prompt_cache_reporting"
    name = "Prompt-cache reporting"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        request = {
            "model": context.model,
            "input": _CACHEABLE_INPUT,
            "max_output_tokens": 16,
        }
        cached_counts: list[int | None] = []
        try:
            for _ in range(_MAX_REQUESTS):
                response = context.client.responses.create(**request)
                details_present, count = cached_tokens(response)
                cached_counts.append(count if details_present else None)
                if isinstance(count, int) and count != 0:
                    break
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
                    "requestsCompleted": len(cached_counts),
                    "maximumRequests": _MAX_REQUESTS,
                    "stablePrefixCharacters": len(_STABLE_PREFIX),
                    "stablePrefixWords": len(_STABLE_PREFIX.split()),
                    "cachedTokensByRequest": cached_counts,
                },
                error=sanitized_error_details(error),
            )

        valid_counts = [count for count in cached_counts if isinstance(count, int)]
        maximum_cached = max(valid_counts, default=None)
        evidence = {
            "requestsCompleted": len(cached_counts),
            "maximumRequests": _MAX_REQUESTS,
            "stablePrefixCharacters": len(_STABLE_PREFIX),
            "stablePrefixWords": len(_STABLE_PREFIX.split()),
            "identicalRequestsUsed": True,
            "cachedTokenMetricPresent": bool(valid_counts),
            "cachedTokens": maximum_cached,
            "cachedTokensByRequest": cached_counts,
        }
        if maximum_cached is not None and maximum_cached > 0:
            evidence["outcome"] = "cached_tokens_observed"
            return ScenarioObservation(status=Status.PASS, evidence=evidence)
        if maximum_cached is not None and maximum_cached < 0:
            evidence["outcome"] = "invalid_cached_token_metric"
            return ScenarioObservation(status=Status.FAIL, evidence=evidence)

        evidence["outcome"] = (
            "cached_tokens_not_observed_after_retries"
            if valid_counts
            else "cached_token_metric_unavailable"
        )
        return ScenarioObservation(status=Status.UNSUPPORTED, evidence=evidence)
