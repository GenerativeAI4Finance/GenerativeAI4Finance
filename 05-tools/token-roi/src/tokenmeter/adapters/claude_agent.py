"""Adapter for the Claude Agent SDK (``claude-agent-sdk``).

Two granularities are available and **must not be combined for the same run**,
or usage is counted twice:

* :func:`instrument` records one row per assistant message — per LLM call.
* :func:`track_result` records the per-model totals carried on the terminal
  ``ResultMessage`` — per run.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from tokenmeter.adapters.base import as_int, emit, field_of, require_module
from tokenmeter.enums import TokenSource
from tokenmeter.records import UsageSample

logger = logging.getLogger("tokenmeter")

MODULE_NAME = "claude_agent_sdk"
INSTALL_HINT = "claude-agent-sdk"

#: Maps the SDK's API-platform label onto the provider string used for pricing.
PROVIDER_BY_PLATFORM: dict[str, str] = {
    "firstparty": "anthropic",
    "mantle": "anthropic",
    "gateway": "anthropic",
    "anthropicaws": "anthropic",
    "anthropicgooglecloud": "anthropic",
    "bedrock": "bedrock",
    "vertex": "vertex",
    "foundry": "foundry",
}
DEFAULT_PROVIDER = "anthropic"

_original_query: Any = None
_original_receive_messages: Any = None
_original_receive_response: Any = None


def samples_from_result(result: Any, *, run_id: str | None = None) -> list[UsageSample]:
    """Build one sample per model from a terminal ``ResultMessage``."""
    model_usage = field_of(result, "model_usage")
    if not model_usage:
        return []
    return [
        _sample_from_model_usage(model, usage, run_id or field_of(result, "session_id"))
        for model, usage in model_usage.items()
    ]


def track_result(result: Any, *, run_id: str | None = None) -> int:
    """Record the per-model totals of a completed run. Returns rows queued."""
    return emit(samples_from_result(result, run_id=run_id))


def sample_from_assistant_message(message: Any) -> UsageSample | None:
    """Build a sample from one ``AssistantMessage``, or ``None`` if it carries no usage."""
    usage = field_of(message, "usage")
    model = field_of(message, "model")
    if not usage or not model:
        return None
    return UsageSample(
        provider=DEFAULT_PROVIDER,
        model=str(model),
        input_tokens=as_int(field_of(usage, "input_tokens")),
        output_tokens=as_int(field_of(usage, "output_tokens")),
        cache_read_tokens=as_int(field_of(usage, "cache_read_input_tokens")),
        cache_write_tokens=as_int(field_of(usage, "cache_creation_input_tokens")),
        token_source=TokenSource.PROVIDER,
        run_id=field_of(message, "session_id"),
    )


def track_assistant_message(message: Any) -> bool:
    """Record one assistant message's usage. Returns whether a row was queued."""
    sample = sample_from_assistant_message(message)
    return False if sample is None else emit([sample]) == 1


def _sample_from_model_usage(model: str, usage: Any, run_id: str | None) -> UsageSample:
    """Convert one ``ModelUsage`` entry into a sample."""
    platform = str(field_of(usage, "provider") or "").strip().lower()
    return UsageSample(
        provider=PROVIDER_BY_PLATFORM.get(platform, DEFAULT_PROVIDER),
        model=str(field_of(usage, "canonicalModel") or model),
        input_tokens=as_int(field_of(usage, "inputTokens")),
        output_tokens=as_int(field_of(usage, "outputTokens")),
        cache_read_tokens=as_int(field_of(usage, "cacheReadInputTokens")),
        cache_write_tokens=as_int(field_of(usage, "cacheCreationInputTokens")),
        token_source=TokenSource.PROVIDER,
        run_id=run_id,
    )


async def _record_stream(stream: AsyncIterator[Any]) -> AsyncIterator[Any]:
    """Pass messages through unchanged, recording usage as it goes."""
    async for message in stream:
        track_assistant_message(message)
        yield message


def _patched_query(**kwargs: Any) -> AsyncIterator[Any]:
    """Replacement for ``claude_agent_sdk.query`` that tees usage."""
    return _record_stream(_original_query(**kwargs))


def _patched_receive_messages(self: Any) -> AsyncIterator[Any]:
    """Replacement for ``ClaudeSDKClient.receive_messages`` that tees usage."""
    return _record_stream(_original_receive_messages(self))


def _patched_receive_response(self: Any) -> AsyncIterator[Any]:
    """Replacement for ``ClaudeSDKClient.receive_response`` that tees usage."""
    return _record_stream(_original_receive_response(self))


def instrument() -> None:
    """Record every assistant message produced by the SDK's streams.

    Call before importing ``query`` or ``ClaudeSDKClient`` by name, since a name
    already bound in the caller's module keeps pointing at the original.
    """
    global _original_query, _original_receive_messages, _original_receive_response
    if _original_query is not None:
        return
    module: Any = require_module(MODULE_NAME, INSTALL_HINT)
    client_class = module.ClaudeSDKClient
    _original_query = module.query
    _original_receive_messages = client_class.receive_messages
    _original_receive_response = client_class.receive_response
    module.query = _patched_query
    client_class.receive_messages = _patched_receive_messages
    client_class.receive_response = _patched_receive_response


def uninstrument() -> None:
    """Undo :func:`instrument`."""
    global _original_query, _original_receive_messages, _original_receive_response
    if _original_query is None:
        return
    module: Any = require_module(MODULE_NAME, INSTALL_HINT)
    module.query = _original_query
    module.ClaudeSDKClient.receive_messages = _original_receive_messages
    module.ClaudeSDKClient.receive_response = _original_receive_response
    _original_query = None
    _original_receive_messages = None
    _original_receive_response = None
