"""Emit one known tokenmeter record through the collector into InfluxDB 3.

Verification harness for the deploy/ stack, not library code. Run it after
`docker compose up -d`, then check the row with deploy/influxdb3/queries.sql.

Creates no schema: InfluxDB is schema-on-write and the database itself is
created out of band (see deploy/influxdb3/bootstrap.md).

    OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=delta \
        python deploy/examples/smoke_emit.py
"""

from __future__ import annotations

import os
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

import tokenmeter
from tokenmeter import ModelCost, OtelConfig, run_context

COLLECTOR_ENDPOINT = os.environ.get("TOKENMETER_OTLP_ENDPOINT", "http://localhost:4317")

RUN_ID = "smoke-1"
AGENT_NAME = "planner"
MODEL = "claude-opus-5"
PROVIDER = "anthropic"

INPUT_TOKENS = 1_000_000
OUTPUT_TOKENS = 1_000
CACHE_READ_TOKENS = 5_000
DURATION_MS = 1830.0

OPUS_COST = ModelCost(
    provider=PROVIDER,
    model=MODEL,
    input_cost_per_1m=Decimal("5"),
    output_cost_per_1m=Decimal("25"),
)


class SmokeNotes(BaseModel):
    """Nested metadata, to prove non-scalar values survive as JSON."""

    model_config = ConfigDict(frozen=True)

    nested: bool = True


class SmokeMetadata(BaseModel):
    """Metadata for the smoke call.

    ``user_id`` is on the collector's ``span_dimensions`` allowlist and so
    becomes its own column; ``notes`` is not, so it lands inside the
    ``attributes`` JSON blob. The contrast is the point of the test.
    """

    model_config = ConfigDict(frozen=True)

    user_id: str = "u-42"
    notes: SmokeNotes = SmokeNotes()


def expected_cost() -> Decimal:
    """The cost the sink should compute, derived the same way PriceBook does.

    Cache reads bill at the library's default 0.10x the input rate.
    """
    per_million = Decimal(1_000_000)
    input_rate = Decimal(OPUS_COST.input_cost_per_1m)
    output_rate = Decimal(OPUS_COST.output_cost_per_1m)
    cache_read_rate = Decimal(OPUS_COST.cache_read_cost_per_1m)
    inputs = Decimal(INPUT_TOKENS) / per_million * input_rate
    outputs = Decimal(OUTPUT_TOKENS) / per_million * output_rate
    cached = Decimal(CACHE_READ_TOKENS) / per_million * cache_read_rate
    return inputs + outputs + cached


def build_otel_config() -> OtelConfig:
    """Bootstrap mode, pointed at the collector, logs off."""
    return OtelConfig(
        configure_sdk=True,
        endpoint=COLLECTOR_ENDPOINT,
        protocol="grpc",
        service_name="tokenmeter-smoke",
        emit_logs=False,
        export_interval_millis=5_000,
    )


def emit_one() -> bool:
    """Track a single call with explicit counts inside a correlation scope."""
    with run_context(run_id=RUN_ID, agent_name=AGENT_NAME):
        emitted = tokenmeter.track(
            None,
            None,
            model=MODEL,
            provider=PROVIDER,
            metadata=SmokeMetadata(),
            input_tokens=INPUT_TOKENS,
            output_tokens=OUTPUT_TOKENS,
            cache_read_tokens=CACHE_READ_TOKENS,
            duration_ms=DURATION_MS,
        )
    return bool(emitted)


def main() -> None:
    """Emit one record and drain the pipeline."""
    temporality = os.environ.get("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE")
    if temporality != "delta":
        print("WARNING: temporality preference is not 'delta'.")
        print("         The cost metric will land in a `counter` field, not `gauge`,")
        print("         and query 8 will silently return nothing.")

    tokenmeter.init(
        otel=build_otel_config(),
        costs=[OPUS_COST],
        environment="dev",
        app_version="0.1.0",
    )
    try:
        emitted = emit_one()
    finally:
        tokenmeter.shutdown(timeout=10.0)

    print(f"emitted={emitted} endpoint={COLLECTOR_ENDPOINT}")
    print(f"expected cost_usd={expected_cost()}")
    print("Now run the assertions in deploy/influxdb3/queries.sql.")


if __name__ == "__main__":
    main()
