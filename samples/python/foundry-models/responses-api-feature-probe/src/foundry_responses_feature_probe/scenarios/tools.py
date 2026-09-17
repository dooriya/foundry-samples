# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json

from foundry_responses_feature_probe.helpers import (
    function_calls,
    get_field,
    response_output_text,
)
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


def _location_tool(name: str, description: str, *, strict: bool) -> dict[str, object]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": strict,
        "parameters": {
            "type": "object",
            "properties": {"location": {"type": "string"}},
            "required": ["location"],
            "additionalProperties": False,
        },
    }


class SingleToolCallScenario:
    capability_id = "single_tool_call"
    name = "Single tool-call round trip"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        tool_name = "get_temperature"
        first = context.client.responses.create(
            model=context.model,
            input=(
                "Call get_temperature exactly once for Seattle. "
                "Use the function result before answering."
            ),
            tools=[
                _location_tool(
                    tool_name,
                    "Return the current temperature for a location.",
                    strict=True,
                )
            ],
            tool_choice={"type": "function", "name": tool_name},
            parallel_tool_calls=False,
        )
        calls = function_calls(first)
        call_valid = False
        if len(calls) == 1 and get_field(calls[0], "name") == tool_name:
            try:
                arguments = json.loads(get_field(calls[0], "arguments", ""))
                call_valid = (
                    isinstance(arguments, dict)
                    and isinstance(arguments.get("location"), str)
                    and bool(get_field(calls[0], "call_id"))
                    and bool(get_field(first, "id"))
                )
            except (TypeError, json.JSONDecodeError):
                call_valid = False

        if not call_valid:
            return ScenarioObservation(
                status=Status.FAIL,
                evidence={
                    "functionCallCount": len(calls),
                    "requestedFunctionObserved": False,
                    "argumentsValid": False,
                    "roundTripCompleted": False,
                },
            )

        call = calls[0]
        final = context.client.responses.create(
            model=context.model,
            previous_response_id=get_field(first, "id"),
            parallel_tool_calls=False,
            tools=[
                _location_tool(
                    tool_name,
                    "Return the current temperature for a location.",
                    strict=True,
                )
            ],
            input=[
                {
                    "type": "function_call_output",
                    "call_id": get_field(call, "call_id"),
                    "output": json.dumps({"temperatureCelsius": 18}),
                }
            ],
        )
        final_text_present = bool(response_output_text(final).strip())
        return ScenarioObservation(
            status=Status.PASS if final_text_present else Status.FAIL,
            evidence={
                "functionCallCount": 1,
                "requestedFunctionObserved": True,
                "argumentsValid": True,
                "functionOutputReturned": True,
                "roundTripCompleted": final_text_present,
            },
        )


class ParallelToolCallsScenario:
    capability_id = "parallel_tool_calls"
    name = "Parallel tool calls"
    max_attempts = 3

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        expected_names = {
            "get_temperature",
            "get_humidity",
            "get_wind_speed",
        }
        max_returned = 0
        max_distinct_requested = 0
        max_unexpected = 0
        attempts_completed = 0

        for _ in range(self.max_attempts):
            response = context.client.responses.create(
                model=context.model,
                input=(
                    "For Seattle, call all three independent functions exactly once: "
                    "get_temperature, get_humidity, and get_wind_speed. "
                    "Return all required function calls in the same response."
                ),
                tools=[
                    _location_tool(
                        "get_temperature",
                        "Return temperature for a location.",
                        strict=False,
                    ),
                    _location_tool(
                        "get_humidity",
                        "Return humidity for a location.",
                        strict=False,
                    ),
                    _location_tool(
                        "get_wind_speed",
                        "Return wind speed for a location.",
                        strict=False,
                    ),
                ],
                tool_choice="required",
                parallel_tool_calls=True,
            )
            attempts_completed += 1
            calls = function_calls(response)
            observed_names = [get_field(call, "name", "") for call in calls]
            distinct_requested = len(set(observed_names) & expected_names)
            unexpected = len([name for name in observed_names if name not in expected_names])
            max_returned = max(max_returned, len(calls))
            max_distinct_requested = max(max_distinct_requested, distinct_requested)
            max_unexpected = max(max_unexpected, unexpected)
            if distinct_requested >= 2 and unexpected == 0:
                return ScenarioObservation(
                    status=Status.PASS,
                    evidence={
                        "outcome": "multiple_distinct_calls_observed",
                        "attemptsCompleted": attempts_completed,
                        "maximumAttempts": self.max_attempts,
                        "requestedFunctionCount": 3,
                        "returnedFunctionCallCount": max_returned,
                        "distinctRequestedFunctionsObserved": max_distinct_requested,
                        "unexpectedFunctionCallCount": max_unexpected,
                    },
                )

        return ScenarioObservation(
            status=Status.UNSUPPORTED,
            evidence={
                "outcome": "multiple_distinct_calls_not_observed",
                "attemptsCompleted": attempts_completed,
                "maximumAttempts": self.max_attempts,
                "requestedFunctionCount": 3,
                "returnedFunctionCallCount": max_returned,
                "distinctRequestedFunctionsObserved": max_distinct_requested,
                "unexpectedFunctionCallCount": max_unexpected,
            },
        )
