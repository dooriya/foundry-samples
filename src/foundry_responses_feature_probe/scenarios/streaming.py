# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from foundry_responses_feature_probe.helpers import get_field
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


class StreamingResponseScenario:
    capability_id = "streaming_response"
    name = "Streaming response"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        stream = context.client.responses.create(
            model=context.model,
            input="Stream a short acknowledgement for a capability diagnostic.",
            stream=True,
        )
        event_types: dict[str, int] = {}
        meaningful_delta_count = 0
        terminal_event = None
        for event in stream:
            event_type = get_field(event, "type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1
            if event_type == "error":
                nested = get_field(event, "error", event)
                code = get_field(nested, "code", "unknown")
                message = get_field(nested, "message", "stream failed")
                raise RuntimeError(f"stream error: code={code} message={message}")
            if event_type == "response.output_text.delta":
                delta = get_field(event, "delta", "")
                if isinstance(delta, str) and delta:
                    meaningful_delta_count += 1
            if event_type in {
                "response.completed",
                "response.failed",
                "response.incomplete",
            }:
                terminal_event = event_type

        passed = meaningful_delta_count > 0 and terminal_event == "response.completed"
        status = Status.PASS if passed else Status.FAIL
        if meaningful_delta_count > 0 and terminal_event == "response.incomplete":
            status = Status.INCONCLUSIVE
        return ScenarioObservation(
            status=status,
            evidence={
                "terminalEvent": terminal_event,
                "completedEventObserved": terminal_event == "response.completed",
                "meaningfulTextDeltaCount": meaningful_delta_count,
                "eventTypeCounts": event_types,
            },
        )
