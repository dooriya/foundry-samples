# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from foundry_responses_feature_probe.scenarios.base import Scenario
from foundry_responses_feature_probe.scenarios.basic import BasicResponseScenario
from foundry_responses_feature_probe.scenarios.prompt_cache import PromptCacheScenario
from foundry_responses_feature_probe.scenarios.reasoning import ReasoningEffortScenario
from foundry_responses_feature_probe.scenarios.streaming import StreamingResponseScenario
from foundry_responses_feature_probe.scenarios.structured import StructuredOutputScenario
from foundry_responses_feature_probe.scenarios.tools import (
    ParallelToolCallsScenario,
    SingleToolCallScenario,
)
from foundry_responses_feature_probe.scenarios.vision import VisionInputScenario

ALL_SCENARIOS: tuple[Scenario, ...] = (
    BasicResponseScenario(),
    StreamingResponseScenario(),
    SingleToolCallScenario(),
    ParallelToolCallsScenario(),
    StructuredOutputScenario(),
    ReasoningEffortScenario(),
    PromptCacheScenario(),
    VisionInputScenario(),
)

SCENARIO_IDS = tuple(scenario.capability_id for scenario in ALL_SCENARIOS)

__all__ = ["ALL_SCENARIOS", "SCENARIO_IDS"]
