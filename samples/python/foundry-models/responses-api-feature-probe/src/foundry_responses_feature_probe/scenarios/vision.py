# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import base64
from importlib import resources

from foundry_responses_feature_probe.helpers import response_output_text
from foundry_responses_feature_probe.models import ScenarioObservation, Status
from foundry_responses_feature_probe.scenarios.base import ScenarioContext


def _fixture_data_url() -> str:
    encoded = (
        resources.files("foundry_responses_feature_probe.fixtures")
        .joinpath("diagnostic-black-square.png.b64")
        .read_text(encoding="ascii")
        .strip()
    )
    decoded = base64.b64decode(encoded, validate=True)
    if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Embedded vision fixture is not a PNG.")
    return f"data:image/png;base64,{encoded}"


class VisionInputScenario:
    capability_id = "vision_input"
    name = "Embedded image input"

    def run(self, context: ScenarioContext) -> ScenarioObservation:
        response = context.client.responses.create(
            model=context.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Inspect the solid-color diagnostic image. "
                                "Reply with exactly BLACK if it is black; "
                                "otherwise reply with exactly NOT_BLACK."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": _fixture_data_url(),
                            "detail": "auto",
                        },
                    ],
                }
            ],
        )
        output_text = response_output_text(response).strip()
        normalized_label = output_text.upper().strip("`'\".,:;!? ")
        label_matched = normalized_label == "BLACK"
        return ScenarioObservation(
            status=Status.PASS if label_matched else Status.FAIL,
            evidence={
                "embeddedFixtureUsed": True,
                "externalUrlUsed": False,
                "expectedLabel": "BLACK",
                "outputTextPresent": bool(output_text),
                "labelMatched": label_matched,
            },
        )
