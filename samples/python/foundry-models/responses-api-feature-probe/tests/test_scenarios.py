# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# cspell:ignore IHDR IIBB IDAT

import base64
import json
import struct
import zlib
from types import SimpleNamespace
from typing import Any

from foundry_responses_feature_probe.models import Status
from foundry_responses_feature_probe.scenarios import ALL_SCENARIOS
from foundry_responses_feature_probe.scenarios.base import ScenarioContext
from foundry_responses_feature_probe.scenarios.basic import BasicResponseScenario
from foundry_responses_feature_probe.scenarios.prompt_cache import PromptCacheScenario
from foundry_responses_feature_probe.scenarios.reasoning import ReasoningEffortScenario
from foundry_responses_feature_probe.scenarios.streaming import StreamingResponseScenario
from foundry_responses_feature_probe.scenarios.structured import StructuredOutputScenario
from foundry_responses_feature_probe.scenarios.tools import (
    ParallelToolCallsScenario,
    SingleToolCallScenario,
)
from foundry_responses_feature_probe.scenarios.vision import (
    VisionInputScenario,
    _fixture_data_url,
)


class FakeResponses:
    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClient:
    def __init__(self, *results: Any) -> None:
        self.responses = FakeResponses(*results)


class FakeApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.param = param
        self.code = "invalid_request_error"
        self.request_id = "request-safe"


def context(*results: Any) -> ScenarioContext:
    return ScenarioContext(client=FakeClient(*results), model="deployment")


def test_registry_has_every_requested_capability_once() -> None:
    assert [scenario.capability_id for scenario in ALL_SCENARIOS] == [
        "basic_response",
        "streaming_response",
        "single_tool_call",
        "parallel_tool_calls",
        "structured_output",
        "reasoning_effort",
        "prompt_cache_reporting",
        "vision_input",
    ]


def test_basic_response_requires_output_text() -> None:
    result = BasicResponseScenario().run(context(SimpleNamespace(output_text="ok")))

    assert result.status is Status.PASS
    assert result.evidence["outputTextPresent"] is True


def test_basic_incomplete_response_is_inconclusive() -> None:
    response = SimpleNamespace(output_text="partial", status="incomplete")

    result = BasicResponseScenario().run(context(response))

    assert result.status is Status.INCONCLUSIVE
    assert result.evidence["responseStatus"] == "incomplete"


def test_streaming_requires_incremental_text_and_completion() -> None:
    events = [
        SimpleNamespace(type="response.created"),
        SimpleNamespace(type="response.output_text.delta", delta="diagnostic "),
        SimpleNamespace(type="response.output_text.delta", delta="response"),
        SimpleNamespace(type="response.completed"),
    ]

    result = StreamingResponseScenario().run(context(events))

    assert result.status is Status.PASS
    assert result.evidence["meaningfulTextDeltaCount"] == 2
    assert result.evidence["completedEventObserved"] is True


def test_streaming_incomplete_after_deltas_is_inconclusive() -> None:
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="partial"),
        SimpleNamespace(type="response.incomplete"),
    ]

    result = StreamingResponseScenario().run(context(events))

    assert result.status is Status.INCONCLUSIVE
    assert result.evidence["terminalEvent"] == "response.incomplete"


def test_single_tool_call_returns_correlated_output_and_gets_final_text() -> None:
    call = SimpleNamespace(
        type="function_call",
        name="get_temperature",
        arguments=json.dumps({"location": "Seattle"}),
        call_id="call-1",
    )
    first = SimpleNamespace(id="response-1", output=[call], output_text="")
    final = SimpleNamespace(id="response-2", output=[], output_text="It is 18 C.")
    scenario_context = context(first, final)

    result = SingleToolCallScenario().run(scenario_context)

    assert result.status is Status.PASS
    first_request, second_request = scenario_context.client.responses.calls
    assert first_request["parallel_tool_calls"] is False
    assert first_request["tools"][0]["strict"] is True
    assert second_request["previous_response_id"] == "response-1"
    assert second_request["parallel_tool_calls"] is False
    assert second_request["input"][0]["type"] == "function_call_output"
    assert second_request["input"][0]["call_id"] == "call-1"
    assert second_request["tools"][0]["strict"] is True


def test_parallel_tools_count_three_distinct_calls_and_use_non_strict_schemas() -> None:
    calls = [
        SimpleNamespace(type="function_call", name=name, call_id=f"call-{index}")
        for index, name in enumerate(
            ("get_temperature", "get_humidity", "get_wind_speed"),
            start=1,
        )
    ]
    scenario_context = context(SimpleNamespace(output=calls))

    result = ParallelToolCallsScenario().run(scenario_context)

    assert result.status is Status.PASS
    request = scenario_context.client.responses.calls[0]
    assert request["parallel_tool_calls"] is True
    assert all(tool["strict"] is False for tool in request["tools"])
    assert result.evidence["returnedFunctionCallCount"] == 3


def test_parallel_tools_retry_until_multiple_distinct_calls_are_observed() -> None:
    single_call = SimpleNamespace(
        output=[SimpleNamespace(type="function_call", name="get_temperature", call_id="call-1")]
    )
    two_calls = SimpleNamespace(
        output=[
            SimpleNamespace(type="function_call", name=name, call_id=f"call-{index}")
            for index, name in enumerate(("get_temperature", "get_humidity"), start=2)
        ]
    )
    scenario_context = context(single_call, two_calls)

    result = ParallelToolCallsScenario().run(scenario_context)

    assert result.status is Status.PASS
    assert result.evidence["outcome"] == "multiple_distinct_calls_observed"
    assert result.evidence["attemptsCompleted"] == 2
    assert result.evidence["distinctRequestedFunctionsObserved"] == 2


def test_parallel_tools_are_unsupported_when_only_one_call_is_observed() -> None:
    responses = [
        SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="get_temperature",
                    call_id=f"call-{index}",
                )
            ]
        )
        for index in range(3)
    ]

    result = ParallelToolCallsScenario().run(context(*responses))

    assert result.status is Status.UNSUPPORTED
    assert result.evidence["outcome"] == "multiple_distinct_calls_not_observed"
    assert result.evidence["attemptsCompleted"] == 3
    assert result.evidence["distinctRequestedFunctionsObserved"] == 1


def test_structured_output_is_locally_validated() -> None:
    payload = {
        "capability": "structured_output",
        "accepted": True,
        "checks": ["shape", "strict"],
    }

    result = StructuredOutputScenario().run(
        context(SimpleNamespace(output_text=json.dumps(payload)))
    )

    assert result.status is Status.PASS
    assert result.evidence == {"jsonParsed": True, "strictSchemaValid": True}


def test_structured_output_rejects_schema_valid_types_with_wrong_constant() -> None:
    payload = {
        "capability": "structured_output",
        "accepted": False,
        "checks": ["shape", "strict"],
    }

    result = StructuredOutputScenario().run(
        context(SimpleNamespace(output_text=json.dumps(payload)))
    )

    assert result.status is Status.FAIL
    assert result.evidence == {"jsonParsed": True, "strictSchemaValid": False}


def test_reasoning_distinguishes_explicit_unsupported_rejection() -> None:
    error = FakeApiError(
        "The reasoning effort parameter is not supported by this model.",
        status_code=400,
        param="reasoning.effort",
    )

    result = ReasoningEffortScenario().run(context(error))

    assert result.status is Status.UNSUPPORTED
    assert result.evidence["outcome"] == "rejected_unsupported"
    assert result.error is not None
    assert result.error["statusCode"] == 400


def test_reasoning_records_accepted_incomplete_response_without_false_rejection() -> None:
    response = SimpleNamespace(
        id="response-1",
        output_text="",
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )

    result = ReasoningEffortScenario().run(context(response))

    assert result.status is Status.PASS
    assert result.evidence["outcome"] == "accepted"
    assert result.evidence["incompleteReason"] == "max_output_tokens"


def test_prompt_cache_passes_only_for_positive_cached_tokens() -> None:
    first = SimpleNamespace(usage=SimpleNamespace(input_tokens_details=None))
    second = SimpleNamespace(
        usage=SimpleNamespace(input_tokens_details=SimpleNamespace(cached_tokens=1024))
    )
    scenario_context = context(first, second)

    result = PromptCacheScenario().run(scenario_context)

    assert result.status is Status.PASS
    assert result.evidence["cachedTokens"] == 1024
    assert result.evidence["stablePrefixWords"] > 1024
    assert result.evidence["cachedTokensByRequest"] == [None, 1024]
    assert len(scenario_context.client.responses.calls) == 2
    assert len({call["input"] for call in scenario_context.client.responses.calls}) == 1
    assert all(call["max_output_tokens"] == 16 for call in scenario_context.client.responses.calls)


def test_prompt_cache_zero_is_unsupported_after_controlled_retries() -> None:
    responses = [
        SimpleNamespace(
            usage=SimpleNamespace(input_tokens_details=SimpleNamespace(cached_tokens=0))
        )
        for _ in range(4)
    ]

    result = PromptCacheScenario().run(context(*responses))

    assert result.status is Status.UNSUPPORTED
    assert result.evidence["outcome"] == "cached_tokens_not_observed_after_retries"
    assert result.evidence["requestsCompleted"] == 4
    assert result.evidence["cachedTokensByRequest"] == [0, 0, 0, 0]


def test_prompt_cache_missing_metric_is_unsupported_after_controlled_retries() -> None:
    result = PromptCacheScenario().run(context(*(SimpleNamespace(usage=None) for _ in range(4))))

    assert result.status is Status.UNSUPPORTED
    assert result.evidence["outcome"] == "cached_token_metric_unavailable"
    assert result.evidence["cachedTokenMetricPresent"] is False
    assert result.evidence["requestsCompleted"] == 4


def test_prompt_cache_negative_metric_fails_validation() -> None:
    first = SimpleNamespace(usage=None)
    second = SimpleNamespace(
        usage=SimpleNamespace(input_tokens_details=SimpleNamespace(cached_tokens=-1))
    )

    result = PromptCacheScenario().run(context(first, second))

    assert result.status is Status.FAIL
    assert result.evidence["outcome"] == "invalid_cached_token_metric"


def test_vision_uses_embedded_png_data_url() -> None:
    scenario_context = context(SimpleNamespace(output_text="BLACK"))

    result = VisionInputScenario().run(scenario_context)

    assert result.status is Status.PASS
    image = scenario_context.client.responses.calls[0]["input"][0]["content"][1]
    assert image["image_url"].startswith("data:image/png;base64,")
    assert image["detail"] == "auto"
    assert result.evidence["externalUrlUsed"] is False
    assert result.evidence["expectedLabel"] == "BLACK"
    assert result.evidence["labelMatched"] is True


def test_vision_fixture_is_a_solid_black_rgb_square() -> None:
    png = base64.b64decode(_fixture_data_url().split(",", maxsplit=1)[1])
    position = 8
    image_data = bytearray()
    width = height = bit_depth = color_type = None
    while position < len(png):
        length = struct.unpack(">I", png[position : position + 4])[0]
        chunk_type = png[position + 4 : position + 8]
        chunk = png[position + 8 : position + 8 + length]
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif chunk_type == b"IDAT":
            image_data.extend(chunk)
        position += length + 12

    assert (width, height, bit_depth, color_type) == (32, 32, 8, 2)
    rows = zlib.decompress(image_data)
    assert len(rows) == height * (1 + width * 3)
    for row_index in range(height):
        row = rows[row_index * (1 + width * 3) : (row_index + 1) * (1 + width * 3)]
        assert row[0] == 0
        assert set(row[1:]) == {0}


def test_vision_fails_when_output_does_not_match_fixture_property() -> None:
    result = VisionInputScenario().run(context(SimpleNamespace(output_text="WHITE")))

    assert result.status is Status.FAIL
    assert result.evidence["outputTextPresent"] is True
    assert result.evidence["labelMatched"] is False
