# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import subprocess

import pytest

from foundry_responses_feature_probe.config import (
    ConfigurationError,
    load_config,
    normalize_responses_base_url,
    normalize_token_scope,
)


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (
            "https://example.services.ai.azure.com/api/projects/project",
            "https://example.services.ai.azure.com/api/projects/project/openai/v1/",
        ),
        (
            "https://example.openai.azure.com/",
            "https://example.openai.azure.com/openai/v1/",
        ),
        (
            "https://example.services.ai.azure.com/openai/v1/",
            "https://example.services.ai.azure.com/openai/v1/",
        ),
        (
            "https://example.services.ai.azure.com/openai/v1/responses",
            "https://example.services.ai.azure.com/openai/v1/",
        ),
        (
            "https://example.services.ai.azure.com/OPENAI/V1",
            "https://example.services.ai.azure.com/openai/v1/",
        ),
    ],
)
def test_normalize_responses_base_url(endpoint: str, expected: str) -> None:
    assert normalize_responses_base_url(endpoint) == expected


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.openai.azure.com",
        "https://user:password@example.openai.azure.com",
        "https://example.openai.azure.com?api-version=secret",
        "https://example.openai.azure.com/#fragment",
        "not-a-url",
    ],
)
def test_normalize_rejects_unsafe_or_invalid_endpoint(endpoint: str) -> None:
    with pytest.raises(ConfigurationError) as error:
        normalize_responses_base_url(endpoint)

    assert "password" not in str(error.value)
    assert "secret" not in str(error.value)


def test_normalize_token_scope_supports_safe_default_audiences() -> None:
    assert normalize_token_scope("https://ai.azure.com/.default") == "https://ai.azure.com/.default"


@pytest.mark.parametrize(
    "scope",
    [
        "http://ai.azure.com/.default",
        "https://user:password@ai.azure.com/.default",
        "https://ai.azure.com/.default?sig=secret",
        "https://ai.azure.com/not-a-default-scope",
    ],
)
def test_normalize_token_scope_rejects_unsafe_values(scope: str) -> None:
    with pytest.raises(ConfigurationError) as error:
        normalize_token_scope(scope)

    assert "password" not in str(error.value)
    assert "secret" not in str(error.value)


def test_load_config_prefers_process_environment_and_defaults_scope() -> None:
    calls: list[list[str]] = []

    def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        raise FileNotFoundError

    config = load_config(
        environ={
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.openai.azure.com",
            "FOUNDRY_MODEL": "deployment",
        },
        command_runner=command_runner,
    )

    assert config.responses_base_url == "https://example.openai.azure.com/openai/v1/"
    assert config.model == "deployment"
    assert config.token_scope == "https://ai.azure.com/.default"
    assert calls == [["azd", "env", "get-value", "FOUNDRY_TOKEN_SCOPE", "--no-prompt"]]


def test_load_config_reads_individual_azd_values() -> None:
    values = {
        "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/p",
        "FOUNDRY_MODEL": "deployment",
        "FOUNDRY_TOKEN_SCOPE": "https://ai.azure.com/.default",
    }
    calls: list[list[str]] = []

    def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        key = command[3]
        return subprocess.CompletedProcess(command, 0, stdout=f"{values[key]}\n", stderr="")

    config = load_config(
        environ={},
        environment_name="diagnostics",
        command_runner=command_runner,
    )

    assert config.model == "deployment"
    assert len(calls) == 3
    assert all("--environment" in command and "diagnostics" in command for command in calls)
    assert all("--no-prompt" in command for command in calls)


def test_load_config_reports_missing_required_names_without_command_output() -> None:
    secret = "do-not-disclose"

    def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=secret)

    with pytest.raises(ConfigurationError) as error:
        load_config(environ={}, command_runner=command_runner)

    assert "FOUNDRY_PROJECT_ENDPOINT" in str(error.value)
    assert "FOUNDRY_MODEL" in str(error.value)
    assert secret not in str(error.value)


def test_load_config_rejects_whitespace_deployment_name() -> None:
    def command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="")

    with pytest.raises(ConfigurationError, match="non-empty deployment name"):
        load_config(
            environ={
                "FOUNDRY_PROJECT_ENDPOINT": "https://example.openai.azure.com",
                "FOUNDRY_MODEL": " ",
            },
            command_runner=command_runner,
        )
