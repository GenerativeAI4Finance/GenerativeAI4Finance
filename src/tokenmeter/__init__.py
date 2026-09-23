"""tokenmeter — emit LLM token usage as OpenTelemetry for cost analytics.

Quick start::

    import tokenmeter
    from tokenmeter import ModelCost, OtelConfig

    tokenmeter.init(
        otel=OtelConfig(configure_sdk=True, endpoint="http://localhost:4317",
                        service_name="checkout-api"),
        costs=[ModelCost(provider="anthropic", model="claude-opus-5",
                         input_cost_per_1m=5, output_cost_per_1m=25)],
        environment="prod",
    )

    tokenmeter.track(prompt, response, model="claude-opus-5", provider="anthropic",
                     metadata={"user_id": 42})

Usage is emitted as OpenTelemetry following the GenAI semantic conventions: the
``gen_ai.client.token.usage`` metric, one span per call, and one log record per
call. Prompt and response text is counted and then discarded — it is never put on
a span, a metric, or a log.
"""

from __future__ import annotations

from tokenmeter.adapters.instrument import instrument, uninstrument
from tokenmeter.api import (
    aflush,
    arecord_sample,
    ashutdown,
    atrack,
    flush,
    get_client,
    init,
    is_initialized,
    record_sample,
    shutdown,
    track,
)
from tokenmeter.client import TokenMeter
from tokenmeter.config import MeterConfig, ModelCost, OtelConfig
from tokenmeter.context import Correlation, current_correlation, run_context
from tokenmeter.enums import CallType, TokenSource
from tokenmeter.errors import (
    AdapterUnavailableError,
    AlreadyInitializedError,
    ExporterUnavailableError,
    NotInitializedError,
    TokenMeterError,
    UnknownAdapterError,
)
from tokenmeter.otel.sink import OtelSink
from tokenmeter.pricing import CostBreakdown, PriceBook
from tokenmeter.records import TokenUsageRecord, UsageSample
from tokenmeter.version import __version__

__all__ = [
    "AdapterUnavailableError",
    "AlreadyInitializedError",
    "CallType",
    "Correlation",
    "CostBreakdown",
    "ExporterUnavailableError",
    "MeterConfig",
    "ModelCost",
    "NotInitializedError",
    "OtelConfig",
    "OtelSink",
    "PriceBook",
    "TokenMeter",
    "TokenMeterError",
    "TokenSource",
    "TokenUsageRecord",
    "UnknownAdapterError",
    "UsageSample",
    "__version__",
    "aflush",
    "arecord_sample",
    "ashutdown",
    "atrack",
    "current_correlation",
    "flush",
    "get_client",
    "init",
    "instrument",
    "is_initialized",
    "record_sample",
    "run_context",
    "shutdown",
    "track",
    "uninstrument",
]
