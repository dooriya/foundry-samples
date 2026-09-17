# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from typing import Any

from foundry_responses_feature_probe.models import ResultsManifest
from foundry_responses_feature_probe.redaction import sanitize_value

JSON_REPORT_NAME = "results.json"
MARKDOWN_REPORT_NAME = "report.md"

_RESULT_LABELS = {
    "pass": "Supported",
    "fail": "Not verified",
    "unsupported": "Unsupported",
    "not_applicable": "Not applicable",
    "skipped": "Not tested",
    "inconclusive": "Not verified",
}

_RESULT_DESCRIPTIONS = {
    "Supported": "the request and capability-specific validation succeeded.",
    "Unsupported": (
        "the service explicitly rejected the capability, or a controlled probe completed "
        "without observing the required behavior."
    ),
    "Not verified": (
        "the probe did not obtain enough evidence to confirm support. This does not mean the "
        "service explicitly rejected the capability."
    ),
    "Not tested": "the scenario was not selected for this run.",
    "Not applicable": "the capability does not apply to the selected target.",
}


def _display_result(status: str) -> str:
    return _RESULT_LABELS[status]


def _markdown_report(document: dict[str, Any]) -> str:
    target = document["target"]
    api_version = "none" if target["apiVersion"] is None else target["apiVersion"]
    lines = [
        "# Responses API Feature Probe Results",
        "",
        "> This report records observed deployment behavior. It is not an authoritative "
        "Microsoft feature-parity certification.",
        "",
        "## Target",
        "",
        f"- Endpoint: `{target['endpoint']}`",
        f"- Deployment/model: `{target['model']}`",
        f"- API family: `{target['apiFamily']}`",
        f"- API version query: `{api_version}`",
        f"- Authentication: `{target['authentication']}`",
        f"- Token scope: `{target['tokenScope']}`",
        f"- Tested at: `{document['testedAt']}`",
        f"- Duration: `{document['durationMs']} ms`",
    ]
    expectations_source = document["expectationsSource"]
    if expectations_source is not None:
        lines.append(
            "- Expectations: "
            f"`{expectations_source['name']}@{expectations_source['version']}` (local file)"
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Capability | Result | Duration |",
            "|---|---|---:|",
        ]
    )
    for scenario in document["scenarios"]:
        lines.append(
            f"| `{scenario['capabilityId']}` | {_display_result(scenario['status'])} | "
            f"{scenario['durationMs']} ms |"
        )

    observed_results = {_display_result(scenario["status"]) for scenario in document["scenarios"]}
    lines.extend(["", "## Result meanings", ""])
    for result, description in _RESULT_DESCRIPTIONS.items():
        if result in observed_results:
            lines.append(f"- **{result}**: {description}")
    lines.extend(["", "## Observations", ""])
    for scenario in document["scenarios"]:
        lines.extend(
            [
                f"### {scenario['name']}",
                "",
                f"- Capability ID: `{scenario['capabilityId']}`",
                f"- Result: **{_display_result(scenario['status'])}**",
            ]
        )
        if scenario["expected"] != "unknown":
            matched = "yes" if scenario["expectationMatched"] else "no"
            lines.extend(
                [
                    f"- Expected result: **{_display_result(scenario['expected'])}**",
                    f"- Matches expectation: **{matched}**",
                ]
            )
        lines.extend(
            [
                "- Evidence:",
                "",
                "```json",
                json.dumps(scenario["observed"], indent=2, sort_keys=True),
                "```",
            ]
        )
        if scenario["error"] is not None:
            lines.extend(
                [
                    "",
                    "- Sanitized error:",
                    "",
                    "```json",
                    json.dumps(scenario["error"], indent=2, sort_keys=True),
                    "```",
                ]
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(manifest: ResultsManifest, output_directory: Path) -> tuple[Path, Path]:
    """Write sanitized JSON and Markdown reports."""

    output_directory.mkdir(parents=True, exist_ok=True)
    document = sanitize_value(manifest.to_dict())
    json_path = output_directory / JSON_REPORT_NAME
    markdown_path = output_directory / MARKDOWN_REPORT_NAME
    json_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown_report(document), encoding="utf-8")
    return json_path, markdown_path
