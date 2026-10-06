"""Module-level API over a single process-wide :class:`~tokenmeter.client.TokenMeter`."""

from __future__ import annotations

import asyncio
import atexit
import logging
import threading
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from tokenmeter.client import TokenMeter
from tokenmeter.config import MeterConfig, ModelCost, OtelConfig
from tokenmeter.enums import CallType
from tokenmeter.errors import AlreadyInitializedError, NotInitializedError
from tokenmeter.otel.sink import OtelSink
from tokenmeter.records import UsageSample

logger = logging.getLogger("tokenmeter")

_client: TokenMeter | None = None
_lock = threading.Lock()
_warned_uninitialized = False


def init(
    otel: OtelConfig | None = None,
    costs: Sequence[ModelCost] = (),
    *,
    environment: str | None = None,
    app_version: str | None = None,
    chars_per_token: float = 4.0,
    sink: OtelSink | None = None,
) -> TokenMeter:
    """Initialise the process-wide meter. Call once at application start-up.

    ``sink`` overrides the default OpenTelemetry sink; it exists so tests can
    supply in-memory providers.
    """
    global _client
    with _lock:
        if _client is not None:
            raise AlreadyInitializedError("tokenmeter.init() has already been called")
        config = MeterConfig(
            otel=otel or OtelConfig(),
            costs=tuple(costs),
            environment=environment,
            app_version=app_version,
            chars_per_token=chars_per_token,
        )
        _client = TokenMeter(config, sink)
    atexit.register(shutdown)
    return _client


def get_client() -> TokenMeter:
    """Return the active client, raising if :func:`init` has not been called."""
    if _client is None:
        raise NotInitializedError("tokenmeter.init() must be called before use")
    return _client


def is_initialized() -> bool:
    """Whether :func:`init` has been called and not yet shut down."""
    return _client is not None


def track(
    prompt: str | None,
    response: str | None,
    model: str,
    provider: str,
    metadata: BaseModel | dict[str, Any] | None = None,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    call_type: CallType = CallType.COMPLETION,
    run_id: str | None = None,
    agent_name: str | None = None,
    timestamp: datetime | None = None,
    duration_ms: float | None = None,
) -> bool:
    """Record one model call. Never raises; returns ``False`` if nothing was emitted."""
    client = _client
    if client is None:
        _warn_uninitialized()
        return False
    return client.track(
        prompt,
        response,
        model,
        provider,
        metadata,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        call_type=call_type,
        run_id=run_id,
        agent_name=agent_name,
        timestamp=timestamp,
        duration_ms=duration_ms,
    )


def record_sample(sample: UsageSample, *, timestamp: datetime | None = None) -> bool:
    """Record a normalised sample produced by an adapter. Never raises."""
    client = _client
    if client is None:
        _warn_uninitialized()
        return False
    return client.record_sample(sample, timestamp=timestamp)


def flush(timeout: float | None = 30.0) -> bool:
    """Flush the telemetry pipeline."""
    return False if _client is None else _client.flush(timeout)


def shutdown(timeout: float | None = 30.0) -> None:
    """Flush and shut down. Idempotent and safe to call at exit."""
    global _client
    with _lock:
        client = _client
        _client = None
    if client is not None:
        client.shutdown(timeout)


async def atrack(
    prompt: str | None,
    response: str | None,
    model: str,
    provider: str,
    metadata: BaseModel | dict[str, Any] | None = None,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    call_type: CallType = CallType.COMPLETION,
    run_id: str | None = None,
    agent_name: str | None = None,
    timestamp: datetime | None = None,
    duration_ms: float | None = None,
) -> bool:
    """Async form of :func:`track`. Emission is in-process, so it never blocks the loop."""
    return track(
        prompt,
        response,
        model,
        provider,
        metadata,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        call_type=call_type,
        run_id=run_id,
        agent_name=agent_name,
        timestamp=timestamp,
        duration_ms=duration_ms,
    )


async def arecord_sample(sample: UsageSample, *, timestamp: datetime | None = None) -> bool:
    """Async form of :func:`record_sample`."""
    return record_sample(sample, timestamp=timestamp)


async def aflush(timeout: float | None = 30.0) -> bool:
    """Async form of :func:`flush`, run off the event loop."""
    return await asyncio.to_thread(flush, timeout)


async def ashutdown(timeout: float | None = 30.0) -> None:
    """Async form of :func:`shutdown`, run off the event loop."""
    await asyncio.to_thread(shutdown, timeout)


def _warn_uninitialized() -> None:
    """Warn once that usage is being dropped because init() was never called."""
    global _warned_uninitialized
    if _warned_uninitialized:
        return
    _warned_uninitialized = True
    logger.warning("tokenmeter: init() has not been called; usage is not being recorded")
