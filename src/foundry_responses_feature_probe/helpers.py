# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Any

_MISSING = object()


def get_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def response_output_items(response: Any) -> list[Any]:
    output = get_field(response, "output", [])
    return list(output) if output is not None else []


def response_output_text(response: Any) -> str:
    direct = get_field(response, "output_text", "")
    if isinstance(direct, str) and direct.strip():
        return direct

    parts: list[str] = []
    for item in response_output_items(response):
        for content in get_field(item, "content", []) or []:
            if get_field(content, "type") == "output_text":
                text = get_field(content, "text", "")
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def function_calls(response: Any) -> list[Any]:
    return [
        item
        for item in response_output_items(response)
        if get_field(item, "type") == "function_call"
    ]


def cached_tokens(response: Any) -> tuple[bool, int | None]:
    usage = get_field(response, "usage")
    if usage is None:
        return False, None
    details = get_field(usage, "input_tokens_details")
    if details is None:
        return False, None
    value = get_field(details, "cached_tokens", _MISSING)
    if value is _MISSING:
        return False, None
    return True, value if type(value) is int else None
