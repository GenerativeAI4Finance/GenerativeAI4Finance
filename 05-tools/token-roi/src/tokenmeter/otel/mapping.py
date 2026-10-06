"""Translate a :class:`~tokenmeter.records.TokenUsageRecord` into OTel attributes.

Attribute mappings are the OpenTelemetry wire format rather than one of our own
data structures, so they are plain mappings — the same documented exception that
applies to the caller's ``metadata`` payload.
"""

from __future__ import annotations

import json
from typing import Any

from opentelemetry.util.types import AttributeValue

from tokenmeter.otel import attributes as attrs
from tokenmeter.pricing import CostBreakdown
from tokenmeter.records import TokenUsageRecord

Attributes = dict[str, AttributeValue]


def span_name(record: TokenUsageRecord) -> str:
    """Span name in the shape the conventions recommend, e.g. ``chat claude-opus-5``."""
    return f"{attrs.operation_name(record.call_type)} {record.model}"


def metric_attributes(record: TokenUsageRecord) -> Attributes:
    """The low-cardinality subset safe to put on a metric.

    Deliberately excludes run id, agent name, environment, and metadata: each of
    those would multiply the metric's time series.
    """
    return {
        attrs.GEN_AI_PROVIDER_NAME: attrs.provider_name(record.provider),
        attrs.GEN_AI_OPERATION_NAME: attrs.operation_name(record.call_type),
        attrs.GEN_AI_REQUEST_MODEL: record.model,
        attrs.GEN_AI_RESPONSE_MODEL: record.model,
    }


def record_attributes(
    record: TokenUsageRecord,
    cost: CostBreakdown | None = None,
    cache_write_attribute: str = attrs.GEN_AI_USAGE_CACHE_WRITE_INPUT_TOKENS,
) -> Attributes:
    """The full attribute set for a span or log record."""
    result: Attributes = {
        **metric_attributes(record),
        attrs.GEN_AI_USAGE_INPUT_TOKENS: record.input_tokens,
        attrs.GEN_AI_USAGE_OUTPUT_TOKENS: record.output_tokens,
        attrs.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS: record.cache_read_tokens,
        cache_write_attribute: record.cache_write_tokens,
        attrs.TOKENMETER_TOKEN_SOURCE: record.token_source.value,
    }
    _set_if_present(result, attrs.GEN_AI_CONVERSATION_ID, record.run_id)
    _set_if_present(result, attrs.GEN_AI_AGENT_NAME, record.agent_name)
    _set_if_present(result, attrs.TOKENMETER_ENVIRONMENT, record.environment)
    _set_if_present(result, attrs.TOKENMETER_APP_VERSION, record.app_version)
    if cost is not None:
        result[attrs.GEN_AI_USAGE_COST] = float(cost.total_cost)
        result[attrs.GEN_AI_USAGE_COST_CURRENCY] = cost.currency
    result.update(metadata_attributes(record.metadata))
    return result


def metadata_attributes(metadata: dict[str, Any]) -> Attributes:
    """Flatten caller metadata under the ``tokenmeter.metadata.`` prefix.

    OTel attribute values must be scalars or homogeneous lists, so anything else
    is JSON-encoded rather than dropped.
    """
    flattened: Attributes = {}
    for key, value in metadata.items():
        flattened[f"{attrs.TOKENMETER_METADATA_PREFIX}{key}"] = _as_attribute_value(value)
    return flattened


def _as_attribute_value(value: Any) -> AttributeValue:
    """Coerce one metadata value into something OTel accepts."""
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple) and all(isinstance(item, str) for item in value):
        return list(value)
    return json.dumps(value, default=str, sort_keys=True)


def _set_if_present(target: Attributes, key: str, value: str | None) -> None:
    """Set an attribute only when the value exists, keeping absent fields absent."""
    if value is not None:
        target[key] = value
