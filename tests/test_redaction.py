# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path

from foundry_responses_feature_probe.models import (
    ResultsManifest,
    ScenarioResult,
    Status,
    TargetMetadata,
)
from foundry_responses_feature_probe.redaction import sanitize_text, sanitize_url
from foundry_responses_feature_probe.reporting import write_reports


def test_sanitize_url_removes_all_credential_bearing_components() -> None:
    sanitized = sanitize_url(
        "https://user:password@example.test/path?sv=1&sig=query-secret#fragment-secret"
    )

    assert sanitized == "https://example.test/path"
    for secret in ("user", "password", "query-secret", "fragment-secret", "sig="):
        assert secret not in sanitized


def test_sanitize_text_redacts_authorization_and_key_material() -> None:
    text = (
        "Authorization: Bearer bearer-secret; "
        "api-key=api-secret x-api-key: x-secret "
        "client_secret=client-secret "
        "token=generic-token-secret "
        "url=https://user:password@example.test/path?sig=query-secret#fragment"
    )

    sanitized = sanitize_text(text)

    for secret in (
        "bearer-secret",
        "api-secret",
        "x-secret",
        "client-secret",
        "generic-token-secret",
        "user",
        "password",
        "query-secret",
        "fragment",
    ):
        assert secret not in sanitized
    assert "Authorization: Bearer [REDACTED]" in sanitized
    assert "https://example.test/path" in sanitized


def test_reports_never_disclose_credential_urls_or_sensitive_errors(tmp_path: Path) -> None:
    manifest = ResultsManifest(
        target=TargetMetadata(
            endpoint="https://user:password@example.test/openai/v1/?sig=query-secret#fragment",
            model="deployment",
            token_scope="https://ai.azure.com/.default",
            request_timeout_seconds=90,
            max_retries=1,
        ),
        tested_at="2026-09-17T08:00:00Z",
        duration_ms=3,
        scenarios=(
            ScenarioResult(
                capability_id="redaction_probe",
                name="Redaction probe",
                status=Status.FAIL,
                expected="unknown",
                observed={"safe": False},
                duration_ms=1,
                error={
                    "message": (
                        "Authorization: Bearer bearer-secret "
                        "api-key=api-secret "
                        "https://user:password@example.test/path?sig=query-secret"
                    )
                },
            ),
        ),
    )

    paths = write_reports(manifest, tmp_path)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for secret in (
        "bearer-secret",
        "api-secret",
        "user:password",
        "query-secret",
        "sig=",
    ):
        assert secret not in combined
