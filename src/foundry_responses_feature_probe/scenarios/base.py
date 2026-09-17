# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass
from typing import Any, Protocol

from foundry_responses_feature_probe.models import ScenarioObservation


@dataclass(frozen=True)
class ScenarioContext:
    """Dependencies shared by every scenario."""

    client: Any
    model: str


class Scenario(Protocol):
    """Runnable capability scenario."""

    capability_id: str
    name: str

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        """Execute the scenario and return sanitized evidence."""
        ...
