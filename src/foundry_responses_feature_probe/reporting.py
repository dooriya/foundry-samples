# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from pathlib import Path
from typing import Any

from foundry_responses_feature_probe.models import ResultsManifest
from foundry_responses_feature_probe.redaction import sanitize_value

JSON_REPORT_NAME = "results.json"
MARKDOWN_REPORT_NAME = "report.md"


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
            "| Capability | Status | Expected | Match | Duration |",
            "|---|---|---|---|---:|",
        ]
    )
    for scenario in document["scenarios"]:
        matched = scenario["expectationMatched"]
        match_text = "unknown" if matched is None else ("yes" if matched else "no")
        lines.append(
            f"| `{scenario['capabilityId']}` | {scenario['status']} | "
            f"{scenario['expected']} | {match_text} | {scenario['durationMs']} ms |"
        )

    lines.extend(["", "## Observations", ""])
    for scenario in document["scenarios"]:
        lines.extend(
            [
                f"### {scenario['name']}",
                "",
                f"- Capability ID: `{scenario['capabilityId']}`",
                f"- Status: `{scenario['status']}`",
                f"- Expected: `{scenario['expected']}`",
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
