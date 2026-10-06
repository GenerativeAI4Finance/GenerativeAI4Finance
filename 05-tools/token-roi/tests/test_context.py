"""Correlation propagation into spans, threads, and asyncio tasks."""

from __future__ import annotations

import asyncio
import threading

from opentelemetry import trace

import tokenmeter
from conftest import Harness
from tokenmeter import run_context
from tokenmeter.otel import attributes as attrs


def _track() -> None:
    tokenmeter.track(
        "p", "r", model="claude-opus-5", provider="anthropic", input_tokens=1, output_tokens=1
    )


def test_run_context_sets_the_conversation_id(meter: Harness) -> None:
    with run_context(run_id="run-42", agent_name="planner"):
        _track()
    span = meter.only_span()
    assert span.attributes[attrs.GEN_AI_CONVERSATION_ID] == "run-42"
    assert span.attributes[attrs.GEN_AI_AGENT_NAME] == "planner"


def test_run_context_generates_an_id_when_none_is_given(meter: Harness) -> None:
    with run_context() as correlation:
        _track()
    assert correlation.run_id is not None
    assert meter.only_span().attributes[attrs.GEN_AI_CONVERSATION_ID] == correlation.run_id


def test_explicit_run_id_beats_the_ambient_one(meter: Harness) -> None:
    with run_context(run_id="ambient"):
        tokenmeter.track(
            "p",
            "r",
            model="claude-opus-5",
            provider="anthropic",
            input_tokens=1,
            output_tokens=1,
            run_id="explicit",
        )
    assert meter.only_span().attributes[attrs.GEN_AI_CONVERSATION_ID] == "explicit"


def test_emitted_span_nests_under_the_active_span(meter: Harness) -> None:
    tracer = meter.tracer_provider.get_tracer("test")
    with tracer.start_as_current_span("parent") as parent:
        _track()
        parent_context = parent.get_span_context()
    usage_span = next(s for s in meter.finished_spans() if s.name == "chat claude-opus-5")
    assert usage_span.parent is not None
    assert usage_span.parent.span_id == parent_context.span_id
    assert usage_span.context.trace_id == parent_context.trace_id


async def _track_concurrently() -> None:
    """Track from three worker threads inside one run context."""
    with run_context(run_id="async-run"):
        await asyncio.gather(*(asyncio.to_thread(_track) for _ in range(3)))


def test_correlation_propagates_into_asyncio_tasks(meter: Harness) -> None:
    asyncio.run(_track_concurrently())
    ids = {span.attributes[attrs.GEN_AI_CONVERSATION_ID] for span in meter.finished_spans()}
    assert ids == {"async-run"}


def test_correlation_does_not_leak_across_threads(meter: Harness) -> None:
    with run_context(run_id="main-run"):
        thread = threading.Thread(target=_track)
        thread.start()
        thread.join()
    spans = meter.finished_spans()
    assert len(spans) == 1
    assert attrs.GEN_AI_CONVERSATION_ID not in spans[0].attributes


def test_current_span_is_untouched_by_tracking(meter: Harness) -> None:
    tracer = meter.tracer_provider.get_tracer("test")
    with tracer.start_as_current_span("parent") as parent:
        _track()
        current = trace.get_current_span().get_span_context()
        assert current.span_id == parent.get_span_context().span_id
