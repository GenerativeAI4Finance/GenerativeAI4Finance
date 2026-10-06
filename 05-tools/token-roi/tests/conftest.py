"""Fixtures wiring tokenmeter to in-memory OpenTelemetry exporters."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import BaseModel, ConfigDict

import tokenmeter
from tokenmeter import ModelCost, OtelConfig, OtelSink
from tokenmeter.otel.provider import OtelProviders, ProviderTrio
from tokenmeter.pricing import PriceBook

OPUS_COST = ModelCost(
    provider="anthropic",
    model="claude-opus-5",
    input_cost_per_1m=Decimal("5"),
    output_cost_per_1m=Decimal("25"),
)


class Harness(BaseModel):
    """The exporters plus the sink under test."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    spans: InMemorySpanExporter
    logs: InMemoryLogRecordExporter
    reader: InMemoryMetricReader
    tracer_provider: TracerProvider
    sink: OtelSink

    def finished_spans(self) -> tuple[Any, ...]:
        """Every span exported so far."""
        return tuple(self.spans.get_finished_spans())

    def only_span(self) -> Any:
        """The single exported span, asserting there is exactly one."""
        spans = self.finished_spans()
        assert len(spans) == 1, f"expected one span, got {len(spans)}"
        return spans[0]

    def log_records(self) -> tuple[Any, ...]:
        """Every log record exported so far."""
        return tuple(record.log_record for record in self.logs.get_finished_logs())

    def metric_points(self, metric_name: str) -> list[Any]:
        """Every data point recorded for one metric."""
        points: list[Any] = []
        data = self.reader.get_metrics_data()
        for resource_metric in data.resource_metrics if data else ():
            for scope_metric in resource_metric.scope_metrics:
                points.extend(_points_of(scope_metric, metric_name))
        return points


def _points_of(scope_metric: Any, metric_name: str) -> list[Any]:
    """Data points belonging to ``metric_name`` within one scope."""
    return [
        point
        for metric in scope_metric.metrics
        if metric.name == metric_name
        for point in metric.data.data_points
    ]


def build_harness(config: OtelConfig, costs: tuple[ModelCost, ...]) -> Harness:
    """Build a sink backed by in-memory exporters."""
    spans = InMemorySpanExporter()
    logs = InMemoryLogRecordExporter()  # type: ignore[no-untyped-call]
    reader = InMemoryMetricReader()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(spans))
    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(logs))
    meter_provider = MeterProvider(metric_readers=[reader])
    providers = OtelProviders(
        config,
        "test",
        ProviderTrio(
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            logger_provider=logger_provider,
        ),
    )
    sink = OtelSink(config, PriceBook(costs), providers)
    return Harness(
        spans=spans,
        logs=logs,
        reader=reader,
        tracer_provider=tracer_provider,
        sink=sink,
    )


@pytest.fixture
def harness() -> Harness:
    """A sink over in-memory exporters, with Opus pricing configured."""
    return build_harness(OtelConfig(), (OPUS_COST,))


@pytest.fixture
def meter(harness: Harness) -> Iterator[Harness]:
    """An initialised process-wide meter using the in-memory harness."""
    tokenmeter.init(
        otel=OtelConfig(),
        costs=[OPUS_COST],
        environment="test",
        app_version="9.9.9",
        sink=harness.sink,
    )
    yield harness
    tokenmeter.shutdown(timeout=1.0)
