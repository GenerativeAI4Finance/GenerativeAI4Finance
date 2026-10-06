"""Module-level API behaviour: lifecycle, guards, and the async wrappers."""

from __future__ import annotations

import pytest

import tokenmeter
from conftest import OPUS_COST, Harness, build_harness
from tokenmeter import AlreadyInitializedError, NotInitializedError, OtelConfig, UsageSample
from tokenmeter.otel import attributes as attrs


def test_calls_before_init_are_dropped_not_raised() -> None:
    assert tokenmeter.is_initialized() is False
    assert tokenmeter.track("p", "r", model="m", provider="p") is False
    assert tokenmeter.flush(timeout=1.0) is False
    with pytest.raises(NotInitializedError):
        tokenmeter.get_client()


def test_second_init_is_rejected(meter: Harness) -> None:
    with pytest.raises(AlreadyInitializedError):
        tokenmeter.init(otel=OtelConfig(), costs=[OPUS_COST], sink=meter.sink)


def test_shutdown_is_idempotent() -> None:
    harness = build_harness(OtelConfig(), (OPUS_COST,))
    tokenmeter.init(otel=OtelConfig(), costs=[OPUS_COST], sink=harness.sink)
    tokenmeter.shutdown(timeout=1.0)
    tokenmeter.shutdown(timeout=1.0)
    assert tokenmeter.is_initialized() is False


def test_record_sample_stamps_environment_and_app_version(meter: Harness) -> None:
    sample = UsageSample(
        provider="anthropic", model="claude-opus-5", input_tokens=10, output_tokens=2
    )
    assert tokenmeter.record_sample(sample) is True
    span = meter.only_span()
    assert span.attributes[attrs.TOKENMETER_ENVIRONMENT] == "test"
    assert span.attributes[attrs.TOKENMETER_APP_VERSION] == "9.9.9"


async def test_async_wrappers_emit_the_same_way(meter: Harness) -> None:
    assert await tokenmeter.atrack(
        "p", "r", model="claude-opus-5", provider="anthropic", input_tokens=3, output_tokens=1
    )
    assert await tokenmeter.arecord_sample(
        UsageSample(provider="anthropic", model="claude-opus-5", input_tokens=1, output_tokens=1)
    )
    assert await tokenmeter.aflush(timeout=1.0) is True
    assert len(meter.finished_spans()) == 2


async def test_ashutdown_stops_the_meter() -> None:
    harness = build_harness(OtelConfig(), (OPUS_COST,))
    tokenmeter.init(otel=OtelConfig(), costs=[OPUS_COST], sink=harness.sink)
    await tokenmeter.ashutdown(timeout=1.0)
    assert tokenmeter.is_initialized() is False


def test_tracking_failures_never_escape(meter: Harness) -> None:
    # An unmappable call type would raise inside mapping; track must swallow it.
    assert tokenmeter.track("p", "r", model="", provider="anthropic") is False
