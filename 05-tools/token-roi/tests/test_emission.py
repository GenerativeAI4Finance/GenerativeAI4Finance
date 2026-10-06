"""End-to-end emission across the three signals."""

from __future__ import annotations

import json

import tokenmeter
from conftest import OPUS_COST, Harness, build_harness
from tokenmeter import OtelConfig
from tokenmeter.otel import attributes as attrs
from tokenmeter.otel.sink import LOG_EVENT_NAME

SENTINEL = "correct-horse-battery-staple"


def _track_one(**overrides: object) -> None:
    kwargs: dict[str, object] = {
        "model": "claude-opus-5",
        "provider": "anthropic",
        "input_tokens": 1000,
        "output_tokens": 100,
        "cache_read_tokens": 600,
        "cache_write_tokens": 200,
        "duration_ms": 1500.0,
        "metadata": {"user_id": 42},
    }
    kwargs.update(overrides)
    assert tokenmeter.track(f"prompt {SENTINEL}", "response", **kwargs) is True  # type: ignore[arg-type]


def test_token_histogram_has_one_point_per_direction(meter: Harness) -> None:
    _track_one()
    tokenmeter.flush(timeout=1.0)
    points = meter.metric_points(attrs.METRIC_TOKEN_USAGE)
    by_type = {point.attributes[attrs.GEN_AI_TOKEN_TYPE]: point for point in points}
    assert set(by_type) == {"input", "output"}
    assert by_type["input"].sum == 1000
    assert by_type["output"].sum == 100


def test_cost_counter_totals_the_priced_usage(meter: Harness) -> None:
    _track_one()
    tokenmeter.flush(timeout=1.0)
    points = meter.metric_points(attrs.METRIC_TOKEN_COST)
    assert len(points) == 1
    assert points[0].value == 0.00905


def test_span_carries_usage_and_back_dated_duration(meter: Harness) -> None:
    _track_one()
    span = meter.only_span()
    assert span.name == "chat claude-opus-5"
    assert span.end_time - span.start_time == 1_500_000_000
    assert span.attributes[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 1000
    assert span.attributes[attrs.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS] == 600
    assert span.attributes[attrs.TOKENMETER_ENVIRONMENT] == "test"
    assert span.attributes[f"{attrs.TOKENMETER_METADATA_PREFIX}user_id"] == 42


def test_span_is_a_point_when_duration_is_unknown(meter: Harness) -> None:
    _track_one(duration_ms=None)
    span = meter.only_span()
    assert span.end_time == span.start_time


def test_one_log_record_per_call(meter: Harness) -> None:
    _track_one()
    records = meter.log_records()
    assert len(records) == 1
    assert records[0].event_name == LOG_EVENT_NAME
    assert records[0].body == "chat claude-opus-5"
    assert records[0].attributes[attrs.GEN_AI_USAGE_OUTPUT_TOKENS] == 100


def test_metric_attributes_never_include_per_call_identifiers(meter: Harness) -> None:
    _track_one(run_id="run-9", agent_name="planner")
    tokenmeter.flush(timeout=1.0)
    for metric_name in (attrs.METRIC_TOKEN_USAGE, attrs.METRIC_TOKEN_COST):
        for point in meter.metric_points(metric_name):
            keys = set(point.attributes)
            assert attrs.GEN_AI_CONVERSATION_ID not in keys
            assert attrs.GEN_AI_AGENT_NAME not in keys
            assert attrs.TOKENMETER_ENVIRONMENT not in keys
            assert not any(k.startswith(attrs.TOKENMETER_METADATA_PREFIX) for k in keys)


def test_prompt_text_never_reaches_any_signal(meter: Harness) -> None:
    tokenmeter.track(
        f"prompt {SENTINEL}",
        f"response {SENTINEL}",
        model="claude-opus-5",
        provider="anthropic",
    )
    tokenmeter.flush(timeout=1.0)
    payload = json.dumps(
        [[span.name, dict(span.attributes or {})] for span in meter.finished_spans()]
        + [[str(record.body), dict(record.attributes or {})] for record in meter.log_records()]
        + [
            [metric_name, dict(point.attributes or {})]
            for metric_name in (attrs.METRIC_TOKEN_USAGE, attrs.METRIC_TOKEN_COST)
            for point in meter.metric_points(metric_name)
        ],
        default=str,
    )
    assert SENTINEL not in payload


def test_signals_can_be_switched_off() -> None:
    config = OtelConfig(emit_spans=False, emit_logs=False)
    harness = build_harness(config, (OPUS_COST,))
    tokenmeter.init(otel=config, costs=[OPUS_COST], sink=harness.sink)
    try:
        _track_one()
        tokenmeter.flush(timeout=1.0)
        assert harness.finished_spans() == ()
        assert harness.log_records() == ()
        assert len(harness.metric_points(attrs.METRIC_TOKEN_USAGE)) == 2
    finally:
        tokenmeter.shutdown(timeout=1.0)


def test_unpriced_model_still_emits_usage_without_cost(meter: Harness) -> None:
    assert tokenmeter.track(
        "p", "r", model="command", provider="cohere", input_tokens=10, output_tokens=5
    )
    span = meter.only_span()
    assert span.attributes[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert attrs.GEN_AI_USAGE_COST not in span.attributes
    tokenmeter.flush(timeout=1.0)
    assert meter.metric_points(attrs.METRIC_TOKEN_COST) == []
