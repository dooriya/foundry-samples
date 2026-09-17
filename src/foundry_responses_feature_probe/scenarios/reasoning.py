# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from foundry_responses_feature_probe.api_errors import (
    classify_api_error,
    sanitized_error_details,
)
from foundry_responses_feature_probe.helpers import get_field, response_output_text
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


class ReasoningEffortScenario:
    capability_id = "reasoning_effort"
    name = "Reasoning-effort control"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        try:
            response = context.client.responses.create(
                model=context.model,
                input="Give a short answer to: what is 17 plus 25?",
                reasoning={"effort": "low"},
            )
        except Exception as error:
            status = classify_api_error(error, ("reasoning", "effort"))
            outcome = {
                Status.UNSUPPORTED: "rejected_unsupported",
                Status.INCONCLUSIVE: "rejected_inconclusive",
            }.get(status, "request_failed")
            return ScenarioObservation(
                status=status,
                evidence={"outcome": outcome},
                error=sanitized_error_details(error),
            )

        response_received = bool(
            get_field(response, "id") or response_output_text(response).strip()
        )
        response_status = get_field(response, "status")
        incomplete = get_field(response, "incomplete_details")
        return ScenarioObservation(
            status=Status.PASS if response_received else Status.INCONCLUSIVE,
            evidence={
                "outcome": "accepted" if response_received else "accepted_without_usable_response",
                "responseReceived": response_received,
                "responseStatus": response_status,
                "incompleteReason": get_field(incomplete, "reason") if incomplete else None,
            },
        )
