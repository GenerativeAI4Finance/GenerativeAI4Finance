"""Provider resolution: attaching to the host app, and bootstrap failure modes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import tokenmeter
from conftest import OPUS_COST
from tokenmeter import ExporterUnavailableError, ModelCost, OtelConfig
from tokenmeter.otel import provider
from tokenmeter.otel.provider import OtelProviders


def test_attach_mode_uses_the_host_providers_and_leaves_them_alive() -> None:
    exporter = InMemorySpanExporter()
    host_provider = TracerProvider()
    host_provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(host_provider)

    tokenmeter.init(otel=OtelConfig(), costs=[OPUS_COST])
    try:
        assert tokenmeter.track(
            "p", "r", model="claude-opus-5", provider="anthropic", input_tokens=5, output_tokens=2
        )
    finally:
        tokenmeter.shutdown(timeout=1.0)

    assert [span.name for span in exporter.get_finished_spans()] == ["chat claude-opus-5"]

    # The host's provider must survive our shutdown.
    host_provider.get_tracer("host").start_span("after-shutdown").end()
    assert [span.name for span in exporter.get_finished_spans()][-1] == "after-shutdown"


def test_bootstrap_without_the_otlp_extra_explains_what_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate the extra being absent rather than asserting on the test
    # environment, so the suite passes whether or not tokenmeter[otlp] is installed.
    def missing(name: str, package: str | None = None) -> object:
        raise ImportError(f"No module named {name!r}")

    monkeypatch.setattr(provider, "importlib", SimpleNamespace(import_module=missing))

    with pytest.raises(ExporterUnavailableError, match=r"tokenmeter\[otlp\]"):
        OtelProviders(OtelConfig(configure_sdk=True, endpoint="http://localhost:4317"), "test")


def test_model_cost_is_hashable_configuration() -> None:
    # Frozen models let MeterConfig hold them in a tuple without defensive copying.
    assert isinstance(OPUS_COST, ModelCost)
    assert OPUS_COST.model_copy() == OPUS_COST
