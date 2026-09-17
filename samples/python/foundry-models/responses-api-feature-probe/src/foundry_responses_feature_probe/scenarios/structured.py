# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json

from jsonschema import ValidationError, validate

from foundry_responses_feature_probe.helpers import response_output_text
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext

_SCHEMA = {
    "type": "object",
    "properties": {
        "capability": {"type": "string", "const": "structured_output"},
        "accepted": {"type": "boolean", "const": True},
        "checks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 2,
        },
    },
    "required": ["capability", "accepted", "checks"],
    "additionalProperties": False,
}


class StructuredOutputScenario:
    capability_id = "structured_output"
    name = "Strict JSON schema output"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        response = context.client.responses.create(
            model=context.model,
            input=(
                "Return the requested diagnostic object. Set capability to structured_output, "
                "accepted to true, and checks to exactly two short strings."
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "diagnostic_result",
                    "strict": True,
                    "schema": _SCHEMA,
                }
            },
        )
        output_text = response_output_text(response)
        parsed = False
        valid = False
        try:
            payload = json.loads(output_text)
            parsed = True
            validate(instance=payload, schema=_SCHEMA)
            valid = True
        except (TypeError, json.JSONDecodeError, ValidationError):
            pass

        return ScenarioObservation(
            status=Status.PASS if valid else Status.FAIL,
            evidence={"jsonParsed": parsed, "strictSchemaValid": valid},
        )
