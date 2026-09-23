"""Adapter for the OpenAI Agents SDK (``openai-agents``).

``input_tokens`` is stored as the *uncached* remainder, because the SDK reports
cached tokens as a subset of the prompt count — see
:func:`tokenmeter.adapters.base.uncached_input`.
"""

from __future__ import annotations

import logging
from typing import Any

from tokenmeter.adapters.base import as_int, emit, field_of, require_module, uncached_input
from tokenmeter.enums import TokenSource
from tokenmeter.records import UsageSample

logger = logging.getLogger("tokenmeter")

try:  # pragma: no cover - exercised only when the SDK is installed
    from agents import RunHooks as _RunHooksBase
    from agents.tracing import TracingProcessor as _TracingProcessorBase
except ImportError:  # pragma: no cover - adapter is unusable without the SDK
    _RunHooksBase = object  # type: ignore[assignment, misc]
    _TracingProcessorBase = object  # type: ignore[assignment, misc]

MODULE_NAME = "agents"
INSTALL_HINT = "openai-agents"
DEFAULT_PROVIDER = "openai"
UNKNOWN_MODEL = "unknown"

_processor: Any = None


def sample_from_usage(
    usage: Any,
    model: str,
    *,
    provider: str = DEFAULT_PROVIDER,
    run_id: str | None = None,
    agent_name: str | None = None,
) -> UsageSample | None:
    """Build a sample from an SDK ``Usage`` object or a raw usage mapping."""
    if usage is None:
        return None
    input_details = field_of(usage, "input_tokens_details")
    cached = as_int(field_of(input_details, "cached_tokens")) if input_details else 0
    cache_write = as_int(field_of(input_details, "cache_write_tokens")) if input_details else 0
    total_input = as_int(field_of(usage, "input_tokens", "prompt_tokens"))
    return UsageSample(
        provider=provider,
        model=model or UNKNOWN_MODEL,
        input_tokens=uncached_input(total_input, cached, cache_write),
        output_tokens=as_int(field_of(usage, "output_tokens", "completion_tokens")),
        cache_read_tokens=cached,
        cache_write_tokens=cache_write,
        token_source=TokenSource.PROVIDER,
        run_id=run_id,
        agent_name=agent_name,
    )


def samples_from_run_result(
    result: Any, *, model: str | None = None, provider: str = DEFAULT_PROVIDER
) -> list[UsageSample]:
    """Build one sample per raw model response in a finished run."""
    resolved = model or _model_of_agent(field_of(result, "last_agent")) or UNKNOWN_MODEL
    agent_name = field_of(field_of(result, "last_agent"), "name")
    samples = [
        sample_from_usage(
            field_of(response, "usage"), resolved, provider=provider, agent_name=agent_name
        )
        for response in field_of(result, "raw_responses") or []
    ]
    return [sample for sample in samples if sample is not None]


def track_run_result(
    result: Any, *, model: str | None = None, provider: str = DEFAULT_PROVIDER
) -> int:
    """Record every model call in a finished run. Returns rows queued."""
    return emit(samples_from_run_result(result, model=model, provider=provider))


def _model_of_agent(agent: Any) -> str | None:
    """Return the agent's model name when it is a plain string."""
    model = field_of(agent, "model")
    return model if isinstance(model, str) else None


def sample_from_span(span: Any, provider: str = DEFAULT_PROVIDER) -> UsageSample | None:
    """Build a sample from a finished ``generation`` or ``response`` trace span."""
    data = field_of(span, "span_data")
    usage = field_of(data, "usage")
    response = field_of(data, "response")
    model = field_of(data, "model") or field_of(response, "model")
    if usage is None and response is not None:
        usage = field_of(response, "usage")
    if usage is None:
        return None
    return sample_from_usage(
        usage, str(model or UNKNOWN_MODEL), provider=provider, run_id=field_of(span, "trace_id")
    )


class TokenMeterTraceProcessor(_TracingProcessorBase):
    """Records usage from generation and response spans as they finish."""

    def __init__(self) -> None:
        super().__init__()
        self.enabled = True

    def on_trace_start(self, trace: Any) -> None:
        """Unused — usage is only known when a span ends."""

    def on_trace_end(self, trace: Any) -> None:
        """Unused — usage is only known when a span ends."""

    def on_span_start(self, span: Any) -> None:
        """Unused — usage is only known when a span ends."""

    def on_span_end(self, span: Any) -> None:
        """Record usage for spans that carry it, unless this processor is disabled."""
        if not self.enabled:
            return
        sample = sample_from_span(span)
        if sample is not None:
            emit([sample])

    def shutdown(self) -> None:
        """Nothing to release; the writer owns its own lifecycle."""

    def force_flush(self) -> None:
        """Nothing buffered here; the writer batches independently."""


class TokenMeterRunHooks(_RunHooksBase):
    """Records one row per LLM call via ``on_llm_end``."""

    def __init__(self, provider: str = DEFAULT_PROVIDER) -> None:
        super().__init__()
        self._provider = provider

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:  # noqa: ARG002
        """Record the usage attached to a finished model response.

        ``context`` is part of the SDK's hook signature and is unused here.
        """
        sample = sample_from_usage(
            field_of(response, "usage"),
            _model_of_agent(agent) or UNKNOWN_MODEL,
            provider=self._provider,
            agent_name=field_of(agent, "name"),
        )
        if sample is not None:
            emit([sample])


def instrument() -> None:
    """Register a trace processor that records every generation span.

    Requires the SDK's tracing to be enabled (the default). If tracing is off,
    pass :func:`run_hooks` to ``Runner.run`` instead.
    """
    global _processor
    if _processor is not None:
        return
    module = require_module(MODULE_NAME, INSTALL_HINT)
    _processor = TokenMeterTraceProcessor()
    module.tracing.add_trace_processor(_processor)


def run_hooks(provider: str = DEFAULT_PROVIDER) -> TokenMeterRunHooks:
    """Build run hooks that record every LLM call, for use when tracing is off."""
    require_module(MODULE_NAME, INSTALL_HINT)
    return TokenMeterRunHooks(provider)


def uninstrument() -> None:
    """Undo :func:`instrument`.

    The SDK has no API for removing a single processor, so the registered
    processor is left in place but made inert.
    """
    global _processor
    if _processor is None:
        return
    _processor.enabled = False
    _processor = None
