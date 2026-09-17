# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

from foundry_responses_feature_probe.redaction import sanitize_url

ENDPOINT_ENV = "FOUNDRY_PROJECT_ENDPOINT"
MODEL_ENV = "FOUNDRY_MODEL"
TOKEN_SCOPE_ENV = "FOUNDRY_TOKEN_SCOPE"
DEFAULT_TOKEN_SCOPE = "https://ai.azure.com/.default"

CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


class ConfigurationError(ValueError):
    """Configuration cannot safely produce a v1 Responses API client."""


@dataclass(frozen=True)
class HarnessConfig:
    """Resolved runtime settings."""

    endpoint: str
    responses_base_url: str
    model: str
    token_scope: str
    request_timeout_seconds: float
    max_retries: int


def _default_command_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )


def _read_azd_value(
    key: str,
    environment_name: str | None,
    command_runner: CommandRunner,
    *,
    required: bool = True,
) -> str | None:
    command = ["azd", "env", "get-value", key, "--no-prompt"]
    if environment_name:
        command.extend(["--environment", environment_name])

    try:
        result = command_runner(command)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if not required:
            return None
        raise ConfigurationError(
            f"{key} is not set in the process environment and azd could not be invoked."
        ) from exc

    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def normalize_responses_base_url(endpoint: str) -> str:
    """Normalize a Foundry project or resource endpoint to an OpenAI v1 base URL."""

    raw = endpoint.strip()
    try:
        parts = urlsplit(raw)
        _ = parts.port
    except ValueError as exc:
        raise ConfigurationError("The Foundry endpoint is not a valid URL.") from exc

    if parts.scheme.lower() != "https" or not parts.hostname:
        raise ConfigurationError("The Foundry endpoint must be an absolute HTTPS URL.")
    if parts.username or parts.password:
        raise ConfigurationError("The Foundry endpoint must not contain user information.")
    if parts.query or parts.fragment:
        raise ConfigurationError(
            "The Foundry endpoint must not contain a query string or fragment."
        )

    path = parts.path.rstrip("/")
    marker = "/openai/v1"
    marker_index = path.lower().rfind(marker)
    if marker_index >= 0:
        suffix = path[marker_index + len(marker) :].strip("/")
        if suffix not in {"", "responses"}:
            raise ConfigurationError(
                "The Foundry endpoint has an unsupported path after /openai/v1."
            )
        path = f"{path[:marker_index]}{marker}"
    else:
        path = f"{path}{marker}"

    return urlunsplit((parts.scheme.lower(), parts.netloc, f"{path}/", "", ""))


def normalize_token_scope(token_scope: str) -> str:
    """Validate a configurable Entra scope without assuming a public-cloud host."""

    raw = token_scope.strip()
    try:
        parts = urlsplit(raw)
        _ = parts.port
    except ValueError as exc:
        raise ConfigurationError("The Entra token scope is not a valid URL.") from exc

    if parts.scheme.lower() != "https" or not parts.hostname:
        raise ConfigurationError("The Entra token scope must be an absolute HTTPS URL.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ConfigurationError(
            "The Entra token scope must not contain credentials, a query string, or a fragment."
        )
    if not parts.path.endswith("/.default"):
        raise ConfigurationError("The Entra token scope must end in '/.default'.")
    return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path, "", ""))


def load_config(
    *,
    environment_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    command_runner: CommandRunner = _default_command_runner,
    request_timeout_seconds: float = 90.0,
    max_retries: int = 1,
) -> HarnessConfig:
    """Resolve settings from the process, local .env, or selected azd environment."""

    if request_timeout_seconds <= 0:
        raise ConfigurationError("Request timeout must be greater than zero.")
    if max_retries < 0:
        raise ConfigurationError("Maximum retries must not be negative.")

    if environ is None:
        load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
        values = os.environ
    else:
        values = environ
    endpoint = values.get(ENDPOINT_ENV) or _read_azd_value(
        ENDPOINT_ENV, environment_name, command_runner
    )
    model = values.get(MODEL_ENV) or _read_azd_value(MODEL_ENV, environment_name, command_runner)
    token_scope = values.get(TOKEN_SCOPE_ENV) or _read_azd_value(
        TOKEN_SCOPE_ENV,
        environment_name,
        command_runner,
        required=False,
    )

    missing = [key for key, value in ((ENDPOINT_ENV, endpoint), (MODEL_ENV, model)) if not value]
    if missing:
        names = ", ".join(missing)
        raise ConfigurationError(
            f"Missing required configuration value(s): {names}. "
            "Set them in the process environment, .env, or with "
            "'azd env set <name> <value>'."
        )

    assert endpoint is not None
    assert model is not None
    base_url = normalize_responses_base_url(endpoint)
    model = model.strip()
    if not model:
        raise ConfigurationError(f"{MODEL_ENV} must be a non-empty deployment name.")
    return HarnessConfig(
        endpoint=sanitize_url(base_url),
        responses_base_url=base_url,
        model=model,
        token_scope=normalize_token_scope(token_scope or DEFAULT_TOKEN_SCOPE),
        request_timeout_seconds=request_timeout_seconds,
        max_retries=max_retries,
    )
