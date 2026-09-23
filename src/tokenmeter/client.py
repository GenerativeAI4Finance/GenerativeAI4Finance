"""The meter client: turns calls into records and emits them as OpenTelemetry."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tokenmeter.config import MeterConfig
from tokenmeter.context import current_correlation
from tokenmeter.counting import CountResult, TokenCounter
from tokenmeter.enums import CallType, TokenSource
from tokenmeter.otel.provider import OtelProviders
from tokenmeter.otel.sink import OtelSink
from tokenmeter.pricing import PriceBook
from tokenmeter.records import TokenUsageRecord, UsageSample
from tokenmeter.version import __version__

logger = logging.getLogger("tokenmeter")

_SOURCE_RANK: dict[TokenSource, int] = {
    TokenSource.HEURISTIC: 0,
    TokenSource.TOKENIZER: 1,
    TokenSource.PROVIDER: 2,
}


class ResolvedCounts(BaseModel):
    """Token counts after reconciling explicit overrides with local counting."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    source: TokenSource


class TokenMeter:
    """Owns the price book, the token counter, and the OpenTelemetry sink."""

    def __init__(self, config: MeterConfig, sink: OtelSink | None = None) -> None:
        self._config = config
        self._counter = TokenCounter(config.chars_per_token)
        self._prices = PriceBook(config.costs)
        self._sink = sink or self._build_sink()
        self._shutdown = False

    def _build_sink(self) -> OtelSink:
        """Build the default sink over the configured providers."""
        providers = OtelProviders(self._config.otel, __version__)
        return OtelSink(self._config.otel, self._prices, providers)

    def track(
        self,
        prompt: str | None,
        response: str | None,
        model: str,
        provider: str,
        metadata: BaseModel | dict[str, Any] | None = None,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        call_type: CallType = CallType.COMPLETION,
        run_id: str | None = None,
        agent_name: str | None = None,
        timestamp: datetime | None = None,
        duration_ms: float | None = None,
    ) -> bool:
        """Record one model call. Never raises; returns ``False`` if nothing was emitted."""
        try:
            counts = self._resolve_counts(
                prompt, response, provider, model, input_tokens, output_tokens
            )
            sample = UsageSample(
                provider=provider,
                model=model,
                input_tokens=counts.input_tokens,
                output_tokens=counts.output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
                token_source=counts.source,
                call_type=call_type,
                duration_ms=duration_ms,
                run_id=run_id,
                agent_name=agent_name,
                metadata=normalize_metadata(metadata),
            )
            return self.record_sample(sample, timestamp=timestamp)
        except Exception:
            logger.exception("tokenmeter: failed to record usage for %s/%s", provider, model)
            return False

    def record_sample(self, sample: UsageSample, *, timestamp: datetime | None = None) -> bool:
        """Record a normalised sample, typically produced by an agent-SDK adapter."""
        try:
            return self._sink.emit(self._to_record(sample, timestamp))
        except Exception:
            logger.exception("tokenmeter: failed to record usage sample")
            return False

    def flush(self, timeout: float | None = 30.0) -> bool:
        """Flush the telemetry pipeline."""
        return False if self._shutdown else self._sink.flush(timeout)

    def shutdown(self, timeout: float | None = 30.0) -> None:
        """Flush and shut down the providers tokenmeter owns. Idempotent."""
        if self._shutdown:
            return
        self._shutdown = True
        self._sink.shutdown(timeout)

    def _to_record(self, sample: UsageSample, timestamp: datetime | None) -> TokenUsageRecord:
        """Stamp a sample with correlation, environment, and timestamp."""
        correlation = current_correlation()
        fields: dict[str, Any] = sample.model_dump()
        fields["provider"] = sample.provider.strip().lower()
        fields["model"] = sample.model.strip().lower()
        fields["run_id"] = sample.run_id or correlation.run_id
        fields["agent_name"] = sample.agent_name or correlation.agent_name
        fields["environment"] = self._config.environment
        fields["app_version"] = self._config.app_version
        if timestamp is not None:
            fields["timestamp"] = timestamp
        return TokenUsageRecord(**fields)

    def _resolve_counts(
        self,
        prompt: str | None,
        response: str | None,
        provider: str,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
    ) -> ResolvedCounts:
        """Prefer caller-supplied counts, counting locally only for what is missing."""
        resolved_input = self._resolve_one(prompt, provider, model, input_tokens)
        resolved_output = self._resolve_one(response, provider, model, output_tokens)
        source = min((resolved_input.source, resolved_output.source), key=_SOURCE_RANK.__getitem__)
        return ResolvedCounts(
            input_tokens=resolved_input.tokens,
            output_tokens=resolved_output.tokens,
            source=source,
        )

    def _resolve_one(
        self, text: str | None, provider: str, model: str, explicit: int | None
    ) -> CountResult:
        """Use the explicit count when given, otherwise count the text."""
        if explicit is not None:
            return CountResult(tokens=explicit, source=TokenSource.PROVIDER)
        return self._counter.count(text, provider, model)


def normalize_metadata(metadata: BaseModel | dict[str, Any] | None) -> dict[str, Any]:
    """Coerce the caller's metadata into a JSON-serialisable mapping."""
    if metadata is None:
        return {}
    if isinstance(metadata, BaseModel):
        return metadata.model_dump(mode="json")
    return dict(metadata)
