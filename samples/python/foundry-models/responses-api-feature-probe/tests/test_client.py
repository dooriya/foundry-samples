# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any

import azure.identity
import openai
import pytest

from foundry_responses_feature_probe.client import live_responses_client
from foundry_responses_feature_probe.config import HarnessConfig


class FakeCredential:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeOpenAI:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.closed = False
        self.close_error: Exception | None = None

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def config() -> HarnessConfig:
    return HarnessConfig(
        endpoint="https://example.test/openai/v1/",
        responses_base_url="https://example.test/openai/v1/",
        model="deployment",
        token_scope="https://ai.azure.com/.default",
        request_timeout_seconds=45,
        max_retries=2,
    )


def test_live_client_passes_token_provider_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = FakeCredential()
    created: list[FakeOpenAI] = []

    def provider() -> str:
        return "not-requested"

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr(
        azure.identity,
        "get_bearer_token_provider",
        lambda actual, scope: (
            provider if actual is credential and scope == "https://ai.azure.com/.default" else None
        ),
    )

    def create_client(**kwargs: Any) -> FakeOpenAI:
        client = FakeOpenAI(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(openai, "OpenAI", create_client)

    with live_responses_client(config()) as client:
        assert client is created[0]
        assert client.kwargs["api_key"] is provider
        assert client.kwargs["base_url"] == "https://example.test/openai/v1/"
        assert client.kwargs["timeout"] == 45
        assert client.kwargs["max_retries"] == 2

    assert created[0].closed is True
    assert credential.closed is True


def test_live_client_closes_credential_when_client_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = FakeCredential()
    fake_client = FakeOpenAI()
    fake_client.close_error = RuntimeError("close failed")

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr(
        azure.identity,
        "get_bearer_token_provider",
        lambda actual, scope: lambda: "not-requested",
    )
    monkeypatch.setattr(openai, "OpenAI", lambda **kwargs: fake_client)

    with pytest.raises(RuntimeError, match="close failed"), live_responses_client(config()):
        pass

    assert credential.closed is True
