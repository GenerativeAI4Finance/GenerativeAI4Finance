"""Configuration models supplied by the host application at ``init`` time."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Cache-write tokens bill at this multiple of the input rate unless overridden.
DEFAULT_CACHE_WRITE_MULTIPLIER = Decimal("1.25")
#: Cache-read tokens bill at this multiple of the input rate unless overridden.
DEFAULT_CACHE_READ_MULTIPLIER = Decimal("0.10")


class OtelConfig(BaseModel):
    """How tokenmeter reaches OpenTelemetry.

    By default it attaches to the providers the host application already
    configured. Set ``configure_sdk=True`` to have tokenmeter build its own SDK
    providers with OTLP exporters, for applications that have no OpenTelemetry
    setup of their own.
    """

    model_config = ConfigDict(frozen=True)

    configure_sdk: bool = False
    endpoint: str | None = None
    protocol: Literal["grpc", "http/protobuf"] = "grpc"
    headers: dict[str, str] = Field(default_factory=dict)
    service_name: str | None = None
    resource_attributes: dict[str, str] = Field(default_factory=dict)
    emit_metrics: bool = True
    emit_spans: bool = True
    emit_logs: bool = True
    export_interval_millis: int = Field(default=60_000, ge=1)
    #: The conventions renamed this attribute; switch to
    #: ``gen_ai.usage.cache_creation.input_tokens`` for backends on the older name.
    cache_write_attribute: str = "gen_ai.usage.cache_write.input_tokens"


class ModelCost(BaseModel):
    """Per-million-token prices for one ``(provider, model)`` pair.

    Cache rates default to Anthropic's published multipliers of the input rate.
    Pass them explicitly for providers that price cached tokens differently.
    """

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_cost_per_1m: Decimal = Field(ge=0)
    output_cost_per_1m: Decimal = Field(ge=0)
    # Always populated by the validator below; the defaults exist so the type
    # signature matches, and are never the values actually used.
    cache_write_cost_per_1m: Decimal = Field(default=Decimal(0), ge=0)
    cache_read_cost_per_1m: Decimal = Field(default=Decimal(0), ge=0)

    @model_validator(mode="before")
    @classmethod
    def _fill_cache_rates(cls, data: Any) -> Any:
        """Derive unset cache rates from the input rate before validation."""
        if not isinstance(data, dict):
            return data
        raw_input = data.get("input_cost_per_1m")
        if raw_input is None:
            return data
        try:
            base = Decimal(str(raw_input))
        except InvalidOperation:
            return data
        filled: dict[str, Any] = dict(data)
        if filled.get("cache_write_cost_per_1m") is None:
            filled["cache_write_cost_per_1m"] = base * DEFAULT_CACHE_WRITE_MULTIPLIER
        if filled.get("cache_read_cost_per_1m") is None:
            filled["cache_read_cost_per_1m"] = base * DEFAULT_CACHE_READ_MULTIPLIER
        return filled

    @property
    def key(self) -> tuple[str, str]:
        """Normalised lookup key for this price entry."""
        return (self.provider.strip().lower(), self.model.strip().lower())


class MeterConfig(BaseModel):
    """The fully resolved configuration held by the active client."""

    model_config = ConfigDict(frozen=True)

    otel: OtelConfig = OtelConfig()
    costs: tuple[ModelCost, ...] = ()
    environment: str | None = None
    app_version: str | None = None
    chars_per_token: float = Field(default=4.0, gt=0)
    flush_timeout_millis: int = Field(default=30_000, ge=1)
