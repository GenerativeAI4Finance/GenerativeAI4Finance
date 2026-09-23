"""Resolve the tracer, meter, and logger tokenmeter emits through.

Two modes:

* **attach** (default) — use whatever providers the host application configured.
  We flush them on shutdown but never shut them down; a library that killed its
  host's telemetry pipeline would be a bug.
* **bootstrap** — build our own SDK providers with OTLP exporters, for apps that
  have no OpenTelemetry setup of their own. These are kept local rather than
  installed as the global providers, so we never clobber a host's configuration.
  Span parenting still works, because trace context is carried in the ambient
  context, not by the provider.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, ConfigDict

from tokenmeter.config import OtelConfig
from tokenmeter.errors import ExporterUnavailableError

logger = logging.getLogger("tokenmeter")

INSTRUMENTATION_NAME = "tokenmeter"


class ProviderTrio(BaseModel):
    """The three signal providers, however they were obtained."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    tracer_provider: Any
    meter_provider: Any
    logger_provider: Any


class OtelProviders:
    """Holds the three signal providers and knows which of them we own."""

    def __init__(
        self, config: OtelConfig, version: str, providers: ProviderTrio | None = None
    ) -> None:
        self._owns_providers = config.configure_sdk and providers is None
        trio = providers if providers is not None else _resolve_trio(config)
        self._trio = trio
        self.tracer = trio.tracer_provider.get_tracer(INSTRUMENTATION_NAME, version)
        self.meter = trio.meter_provider.get_meter(INSTRUMENTATION_NAME, version)
        self.logger = trio.logger_provider.get_logger(INSTRUMENTATION_NAME, version)

    def force_flush(self, timeout_millis: int) -> None:
        """Flush every provider that supports flushing."""
        for provider in self._providers:
            _call_if_supported(provider, "force_flush", timeout_millis)

    def shutdown(self, timeout_millis: int) -> None:
        """Flush, then shut down only the providers we created ourselves."""
        self.force_flush(timeout_millis)
        if not self._owns_providers:
            return
        for provider in self._providers:
            _call_if_supported(provider, "shutdown")

    @property
    def _providers(self) -> tuple[Any, Any, Any]:
        """The three providers in a fixed order."""
        return (
            self._trio.tracer_provider,
            self._trio.meter_provider,
            self._trio.logger_provider,
        )


def _resolve_trio(config: OtelConfig) -> ProviderTrio:
    """Bootstrap our own providers, or attach to the host application's."""
    if not config.configure_sdk:
        return ProviderTrio(
            tracer_provider=trace.get_tracer_provider(),
            meter_provider=metrics.get_meter_provider(),
            logger_provider=get_logger_provider(),
        )
    resource = _resource_for(config)
    return ProviderTrio(
        tracer_provider=_build_tracer_provider(config, resource),
        meter_provider=_build_meter_provider(config, resource),
        logger_provider=_build_logger_provider(config, resource),
    )


def _call_if_supported(provider: Any, method_name: str, *args: Any) -> None:
    """Call a provider lifecycle method, ignoring providers that lack it."""
    method = getattr(provider, method_name, None)
    if method is None:
        return
    try:
        method(*args)
    except Exception:
        logger.warning("tokenmeter: %s failed on %r", method_name, provider, exc_info=True)


def _resource_for(config: OtelConfig) -> Resource:
    """Build the resource describing this service."""
    attributes: dict[str, Any] = dict(config.resource_attributes)
    if config.service_name is not None:
        attributes["service.name"] = config.service_name
    return Resource.create(attributes)


def _build_tracer_provider(config: OtelConfig, resource: Resource) -> TracerProvider:
    """Build a tracer provider exporting over OTLP."""
    provider = TracerProvider(resource=resource)
    exporter = _load_exporter(config, "span")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def _build_meter_provider(config: OtelConfig, resource: Resource) -> MeterProvider:
    """Build a meter provider exporting over OTLP on the configured interval."""
    exporter = _load_exporter(config, "metric")
    reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=config.export_interval_millis
    )
    return MeterProvider(resource=resource, metric_readers=[reader])


def _build_logger_provider(config: OtelConfig, resource: Resource) -> LoggerProvider:
    """Build a logger provider exporting over OTLP."""
    provider = LoggerProvider(resource=resource)
    exporter = _load_exporter(config, "log")
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    return provider


_EXPORTER_PATHS: dict[tuple[str, str], tuple[str, str]] = {
    ("grpc", "span"): ("opentelemetry.exporter.otlp.proto.grpc.trace_exporter", "OTLPSpanExporter"),
    ("grpc", "metric"): (
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter",
        "OTLPMetricExporter",
    ),
    ("grpc", "log"): (
        "opentelemetry.exporter.otlp.proto.grpc._log_exporter",
        "OTLPLogExporter",
    ),
    ("http/protobuf", "span"): (
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "OTLPSpanExporter",
    ),
    ("http/protobuf", "metric"): (
        "opentelemetry.exporter.otlp.proto.http.metric_exporter",
        "OTLPMetricExporter",
    ),
    ("http/protobuf", "log"): (
        "opentelemetry.exporter.otlp.proto.http._log_exporter",
        "OTLPLogExporter",
    ),
}


def _load_exporter(config: OtelConfig, signal: str) -> Any:
    """Instantiate the OTLP exporter for one signal, or explain what is missing."""
    module_path, class_name = _EXPORTER_PATHS[(config.protocol, signal)]
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ExporterUnavailableError(
            f"OTLP {signal} export over {config.protocol} needs an exporter package; "
            "run `pip install tokenmeter[otlp]`"
        ) from exc
    exporter_class = getattr(module, class_name)
    if config.endpoint is None:
        return exporter_class(headers=config.headers or None)
    return exporter_class(endpoint=config.endpoint, headers=config.headers or None)
