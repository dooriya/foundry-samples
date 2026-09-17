# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from foundry_responses_feature_probe.helpers import get_field, response_output_text
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


class BasicResponseScenario:
    capability_id = "basic_response"
    name = "Basic non-streaming response"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        response = context.client.responses.create(
            model=context.model,
            input="Reply with a short acknowledgement for a capability diagnostic.",
        )
        text_present = bool(response_output_text(response).strip())
        response_status = get_field(response, "status")
        if response_status == "incomplete":
            status = Status.INCONCLUSIVE
        else:
            status = Status.PASS if text_present and response_status != "failed" else Status.FAIL
        return ScenarioObservation(
            status=status,
            evidence={
                "responseReceived": True,
                "responseStatus": response_status,
                "outputTextPresent": text_present,
            },
        )
