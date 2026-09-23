"""Record-to-attribute mapping."""

from __future__ import annotations

import json

from conftest import OPUS_COST
from tokenmeter import CallType, TokenSource
from tokenmeter.otel import attributes as attrs
from tokenmeter.otel.mapping import metric_attributes, record_attributes, span_name
from tokenmeter.pricing import PriceBook
from tokenmeter.records import TokenUsageRecord

HIGH_CARDINALITY_KEYS = (
    attrs.GEN_AI_CONVERSATION_ID,
    attrs.GEN_AI_AGENT_NAME,
    attrs.TOKENMETER_ENVIRONMENT,
    attrs.TOKENMETER_APP_VERSION,
)


def _record(**overrides: object) -> TokenUsageRecord:
    fields: dict[str, object] = {
        "provider": "anthropic",
        "model": "claude-opus-5",
        "input_tokens": 1000,
        "output_tokens": 100,
        "cache_read_tokens": 600,
        "cache_write_tokens": 200,
        "token_source": TokenSource.PROVIDER,
        "run_id": "run-1",
        "agent_name": "planner",
        "environment": "prod",
        "app_version": "1.2.3",
    }
    fields.update(overrides)
    return TokenUsageRecord(**fields)  # type: ignore[arg-type]


def test_span_name_follows_convention_shape() -> None:
    assert span_name(_record()) == "chat claude-opus-5"
    assert span_name(_record(call_type=CallType.EMBEDDING)) == "embeddings claude-opus-5"


def test_metric_attributes_stay_low_cardinality() -> None:
    result = metric_attributes(_record(metadata={"user_id": 7}))
    assert set(result) == {
        attrs.GEN_AI_PROVIDER_NAME,
        attrs.GEN_AI_OPERATION_NAME,
        attrs.GEN_AI_REQUEST_MODEL,
        attrs.GEN_AI_RESPONSE_MODEL,
    }
    for key in HIGH_CARDINALITY_KEYS:
        assert key not in result
    assert not any(k.startswith(attrs.TOKENMETER_METADATA_PREFIX) for k in result)


def test_record_attributes_carry_usage_correlation_and_cost() -> None:
    record = _record()
    cost = PriceBook([OPUS_COST]).cost_for(record)
    result = record_attributes(record, cost)
    assert result[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 1000
    assert result[attrs.GEN_AI_USAGE_OUTPUT_TOKENS] == 100
    assert result[attrs.GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS] == 600
    assert result[attrs.GEN_AI_USAGE_CACHE_WRITE_INPUT_TOKENS] == 200
    assert result[attrs.GEN_AI_CONVERSATION_ID] == "run-1"
    assert result[attrs.GEN_AI_AGENT_NAME] == "planner"
    assert result[attrs.TOKENMETER_ENVIRONMENT] == "prod"
    assert result[attrs.TOKENMETER_APP_VERSION] == "1.2.3"
    assert result[attrs.TOKENMETER_TOKEN_SOURCE] == "provider"
    assert result[attrs.GEN_AI_USAGE_COST] == 0.00905
    assert result[attrs.GEN_AI_USAGE_COST_CURRENCY] == "USD"


def test_absent_fields_are_omitted_rather_than_null() -> None:
    result = record_attributes(_record(run_id=None, agent_name=None, environment=None))
    assert attrs.GEN_AI_CONVERSATION_ID not in result
    assert attrs.GEN_AI_AGENT_NAME not in result
    assert attrs.TOKENMETER_ENVIRONMENT not in result


def test_cost_attributes_absent_without_a_price() -> None:
    result = record_attributes(_record(), None)
    assert attrs.GEN_AI_USAGE_COST not in result
    assert attrs.GEN_AI_USAGE_COST_CURRENCY not in result


def test_metadata_is_flattened_and_coerced() -> None:
    metadata = {
        "user_id": 42,
        "flag": True,
        "ratio": 0.5,
        "tier": "gold",
        "tags": ["a", "b"],
        "nested": {"a": 1},
        "mixed": [1, "two"],
    }
    result = record_attributes(_record(metadata=metadata))
    prefix = attrs.TOKENMETER_METADATA_PREFIX
    assert result[f"{prefix}user_id"] == 42
    assert result[f"{prefix}flag"] is True
    assert result[f"{prefix}ratio"] == 0.5
    assert result[f"{prefix}tier"] == "gold"
    assert result[f"{prefix}tags"] == ["a", "b"]
    assert json.loads(str(result[f"{prefix}nested"])) == {"a": 1}
    assert json.loads(str(result[f"{prefix}mixed"])) == [1, "two"]


def test_cache_write_attribute_is_switchable() -> None:
    result = record_attributes(_record(), None, attrs.GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS)
    assert result[attrs.GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS] == 200
    assert attrs.GEN_AI_USAGE_CACHE_WRITE_INPUT_TOKENS not in result


def test_provider_names_map_to_convention_values() -> None:
    assert attrs.provider_name("Anthropic") == "anthropic"
    assert attrs.provider_name("vertex") == "gcp.vertex_ai"
    assert attrs.provider_name("bedrock") == "aws.bedrock"
    assert attrs.provider_name("foundry") == "azure.ai.inference"


def test_unmapped_provider_passes_through() -> None:
    assert attrs.provider_name("Together") == "together"
