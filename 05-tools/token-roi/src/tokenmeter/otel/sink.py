"""The OpenTelemetry sink: one metric pair, one span, and one log per record."""

from __future__ import annotations

import logging

from opentelemetry._logs import SeverityNumber
from opentelemetry.trace import SpanKind

from tokenmeter.config import OtelConfig
from tokenmeter.otel import attributes as attrs
from tokenmeter.otel.mapping import Attributes, metric_attributes, record_attributes, span_name
from tokenmeter.otel.provider import OtelProviders
from tokenmeter.pricing import CostBreakdown, PriceBook
from tokenmeter.records import TokenUsageRecord

logger = logging.getLogger("tokenmeter")

_NANOS_PER_SECOND = 1_000_000_000
_NANOS_PER_MILLI = 1_000_000
LOG_EVENT_NAME = "tokenmeter.token_usage"


class OtelSink:
    """Emits one record as GenAI-convention telemetry."""

    def __init__(self, config: OtelConfig, prices: PriceBook, providers: OtelProviders) -> None:
        self._config = config
        self._prices = prices
        self._providers = providers
        self._token_histogram = providers.meter.create_histogram(
            attrs.METRIC_TOKEN_USAGE,
            unit=attrs.UNIT_TOKEN,
            description="Number of input and output tokens used.",
        )
        self._cost_counter = providers.meter.create_counter(
            attrs.METRIC_TOKEN_COST,
            unit=attrs.UNIT_COST,
            description="Cost of token usage, priced from the configured model costs.",
        )

    def emit(self, record: TokenUsageRecord) -> bool:
        """Emit one record across the configured signals."""
        cost = self._cost_for(record)
        if self._config.emit_metrics:
            self._emit_metrics(record, cost)
        full_attributes = record_attributes(record, cost, self._config.cache_write_attribute)
        if self._config.emit_spans:
            self._emit_span(record, full_attributes)
        if self._config.emit_logs:
            self._emit_log(record, full_attributes)
        return True

    def flush(self, timeout: float | None) -> bool:
        """Flush every provider. Returns ``True`` once the flush has been requested."""
        self._providers.force_flush(_millis(timeout))
        return True

    def shutdown(self, timeout: float | None) -> None:
        """Flush and shut down the providers we own."""
        self._providers.shutdown(_millis(timeout))

    def _cost_for(self, record: TokenUsageRecord) -> CostBreakdown | None:
        """Price a record, warning once when its model has no configured cost."""
        self._prices.warn_if_unknown(record.provider, record.model)
        return self._prices.cost_for(record)

    def _emit_metrics(self, record: TokenUsageRecord, cost: CostBreakdown | None) -> None:
        """Record the token histogram points and the cost counter."""
        base = metric_attributes(record)
        self._token_histogram.record(
            record.input_tokens, {**base, attrs.GEN_AI_TOKEN_TYPE: attrs.TOKEN_TYPE_INPUT}
        )
        self._token_histogram.record(
            record.output_tokens, {**base, attrs.GEN_AI_TOKEN_TYPE: attrs.TOKEN_TYPE_OUTPUT}
        )
        if cost is not None:
            self._cost_counter.add(float(cost.total_cost), base)

    def _emit_span(self, record: TokenUsageRecord, attributes: Attributes) -> None:
        """Emit a client span for the call, parented to whatever span is active."""
        end_time = int(record.timestamp.timestamp() * _NANOS_PER_SECOND)
        start_time = end_time - int((record.duration_ms or 0.0) * _NANOS_PER_MILLI)
        span = self._providers.tracer.start_span(
            span_name(record),
            kind=SpanKind.CLIENT,
            attributes=attributes,
            start_time=start_time,
        )
        span.end(end_time)

    def _emit_log(self, record: TokenUsageRecord, attributes: Attributes) -> None:
        """Emit a log record carrying the same attributes as the span."""
        self._providers.logger.emit(
            timestamp=int(record.timestamp.timestamp() * _NANOS_PER_SECOND),
            severity_number=SeverityNumber.INFO,
            severity_text="INFO",
            body=span_name(record),
            attributes=attributes,
            event_name=LOG_EVENT_NAME,
        )


def _millis(timeout: float | None) -> int:
    """Convert a timeout in seconds to whole milliseconds."""
    return 30_000 if timeout is None else max(1, int(timeout * 1000))
