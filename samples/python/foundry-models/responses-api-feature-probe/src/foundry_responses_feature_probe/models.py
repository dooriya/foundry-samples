# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    """Observed outcome for a diagnostic scenario."""

    PASS = "pass"
    FAIL = "fail"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED = "skipped"
    INCONCLUSIVE = "inconclusive"


EXPECTED_UNKNOWN = "unknown"


@dataclass(frozen=True)
class TargetMetadata:
    """Sanitized metadata for the deployment under test."""

    endpoint: str
    model: str
    token_scope: str
    request_timeout_seconds: float
    max_retries: int
    api_family: str = "openai/v1"
    api_version: None = None
    authentication: str = "default_azure_credential"

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "apiFamily": self.api_family,
            "apiVersion": self.api_version,
            "authentication": self.authentication,
            "tokenScope": self.token_scope,
            "requestTimeoutSeconds": self.request_timeout_seconds,
            "maxRetries": self.max_retries,
        }


@dataclass(frozen=True)
class ExpectationsSource:
    """Identity of an optional local expectations document."""

    name: str
    version: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": "local_file", "name": self.name, "version": self.version}


@dataclass(frozen=True)
class ExpectationSet:
    """Expected statuses keyed by capability ID."""

    source: ExpectationsSource | None = None
    statuses: dict[str, str] = field(default_factory=dict)

    def status_for(self, capability_id: str) -> str:
        return self.statuses.get(capability_id, EXPECTED_UNKNOWN)


@dataclass(frozen=True)
class ScenarioObservation:
    """Scenario output before timing and expectations are attached."""

    status: Status
    evidence: dict[str, Any]
    error: dict[str, Any] | None = None


@dataclass(frozen=True)
class ScenarioResult:
    """Versioned report entry for one capability."""

    capability_id: str
    name: str
    status: Status
    expected: str
    observed: dict[str, Any]
    duration_ms: int
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        matched = None if self.expected == EXPECTED_UNKNOWN else self.expected == self.status.value
        return {
            "capabilityId": self.capability_id,
            "name": self.name,
            "status": self.status.value,
            "expected": self.expected,
            "expectationMatched": matched,
            "durationMs": self.duration_ms,
            "observed": self.observed,
            "error": self.error,
        }


@dataclass(frozen=True)
class ResultsManifest:
    """Complete machine-readable diagnostic report."""

    target: TargetMetadata
    tested_at: str
    duration_ms: int
    scenarios: tuple[ScenarioResult, ...]
    expectations_source: ExpectationsSource | None = None
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        counts = {status.value: 0 for status in Status}
        for result in self.scenarios:
            counts[result.status.value] += 1

        return {
            "schemaVersion": self.schema_version,
            "reportType": "observed_capability_diagnostics",
            "notice": (
                "Observed deployment behavior only; this report is not an authoritative "
                "Microsoft feature-parity certification."
            ),
            "target": self.target.to_dict(),
            "testedAt": self.tested_at,
            "durationMs": self.duration_ms,
            "expectationsSource": (
                self.expectations_source.to_dict() if self.expectations_source else None
            ),
            "summary": counts,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }
