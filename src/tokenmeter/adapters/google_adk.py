"""Adapter for the Google Agent Development Kit (``google-adk``).

``input_tokens`` is stored as the *uncached* remainder, because Gemini reports
``cached_content_token_count`` as a subset of ``prompt_token_count`` — see
:func:`tokenmeter.adapters.base.uncached_input`. Thinking tokens are folded into
``output_tokens``, which is how they are billed.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

from tokenmeter.adapters.base import as_int, emit, field_of, require_module, uncached_input
from tokenmeter.enums import TokenSource
from tokenmeter.records import UsageSample

logger = logging.getLogger("tokenmeter")

MODULE_NAME = "google.adk"
INSTALL_HINT = "google-adk"
DEFAULT_PROVIDER = "google"
UNKNOWN_MODEL = "unknown"

_original_run_async: Any = None
_original_run: Any = None


def sample_from_event(event: Any, provider: str = DEFAULT_PROVIDER) -> UsageSample | None:
    """Build a sample from an ADK ``Event``, or ``None`` if it carries no usage."""
    usage = field_of(event, "usage_metadata")
    if usage is None or field_of(event, "partial") is True:
        return None
    cached = as_int(field_of(usage, "cached_content_token_count"))
    prompt = as_int(field_of(usage, "prompt_token_count"))
    tool_prompt = as_int(field_of(usage, "tool_use_prompt_token_count"))
    output = as_int(field_of(usage, "candidates_token_count")) + as_int(
        field_of(usage, "thoughts_token_count")
    )
    return UsageSample(
        provider=provider,
        model=str(field_of(event, "model_version") or UNKNOWN_MODEL),
        input_tokens=uncached_input(prompt, cached) + tool_prompt,
        output_tokens=output,
        cache_read_tokens=cached,
        token_source=TokenSource.PROVIDER,
        run_id=field_of(event, "invocation_id"),
        agent_name=field_of(event, "author"),
    )


def track_event(event: Any, provider: str = DEFAULT_PROVIDER) -> bool:
    """Record one ADK event's usage. Returns whether a row was queued."""
    sample = sample_from_event(event, provider)
    return False if sample is None else emit([sample]) == 1


async def _record_events(stream: AsyncIterator[Any]) -> AsyncIterator[Any]:
    """Pass events through unchanged, recording usage as it goes."""
    async for event in stream:
        track_event(event)
        yield event


def _record_events_sync(stream: Iterator[Any]) -> Iterator[Any]:
    """Synchronous form of :func:`_record_events`."""
    for event in stream:
        track_event(event)
        yield event


def _patched_run_async(self: Any, **kwargs: Any) -> AsyncIterator[Any]:
    """Replacement for ``Runner.run_async`` that tees usage."""
    return _record_events(_original_run_async(self, **kwargs))


def _patched_run(self: Any, **kwargs: Any) -> Iterator[Any]:
    """Replacement for ``Runner.run`` that tees usage."""
    return _record_events_sync(_original_run(self, **kwargs))


def instrument() -> None:
    """Record usage for every event produced by ``Runner.run`` / ``Runner.run_async``."""
    global _original_run_async, _original_run
    if _original_run_async is not None:
        return
    runner_class = require_module(f"{MODULE_NAME}.runners", INSTALL_HINT).Runner
    _original_run_async = runner_class.run_async
    _original_run = runner_class.run
    runner_class.run_async = _patched_run_async
    runner_class.run = _patched_run


def uninstrument() -> None:
    """Undo :func:`instrument`."""
    global _original_run_async, _original_run
    if _original_run_async is None:
        return
    runner_class = require_module(f"{MODULE_NAME}.runners", INSTALL_HINT).Runner
    runner_class.run_async = _original_run_async
    runner_class.run = _original_run
    _original_run_async = None
    _original_run = None
