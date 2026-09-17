# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from foundry_responses_feature_probe.config import HarnessConfig


@contextmanager
def live_responses_client(config: HarnessConfig) -> Iterator[Any]:
    """Create an OpenAI client backed by an automatically refreshed Entra token."""

    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import OpenAI

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, config.token_scope)
    client = OpenAI(
        base_url=config.responses_base_url,
        api_key=token_provider,
        timeout=config.request_timeout_seconds,
        max_retries=config.max_retries,
    )
    try:
        yield client
    finally:
        try:
            client.close()
        finally:
            credential.close()
