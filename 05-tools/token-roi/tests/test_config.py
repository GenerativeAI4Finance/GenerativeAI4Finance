"""Configuration model behaviour."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from tokenmeter import ModelCost, OtelConfig


def test_cache_rates_default_from_input_rate() -> None:
    cost = ModelCost(
        provider="anthropic",
        model="claude-opus-5",
        input_cost_per_1m=Decimal("5"),
        output_cost_per_1m=Decimal("25"),
    )
    assert cost.cache_write_cost_per_1m == Decimal("6.25")
    assert cost.cache_read_cost_per_1m == Decimal("0.50")


def test_explicit_cache_rates_are_kept() -> None:
    cost = ModelCost(
        provider="openai",
        model="gpt-4o",
        input_cost_per_1m=Decimal("2.50"),
        output_cost_per_1m=Decimal("10"),
        cache_read_cost_per_1m=Decimal("1.25"),
    )
    assert cost.cache_read_cost_per_1m == Decimal("1.25")
    assert cost.cache_write_cost_per_1m == Decimal("3.125")


def test_key_is_normalised() -> None:
    cost = ModelCost(
        provider="  Anthropic ",
        model="Claude-Opus-5",
        input_cost_per_1m=Decimal("5"),
        output_cost_per_1m=Decimal("25"),
    )
    assert cost.key == ("anthropic", "claude-opus-5")


def test_negative_rate_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ModelCost(
            provider="anthropic",
            model="claude-opus-5",
            input_cost_per_1m=Decimal("-1"),
            output_cost_per_1m=Decimal("25"),
        )


def test_otel_config_defaults_to_attach_mode() -> None:
    config = OtelConfig()
    assert config.configure_sdk is False
    assert config.protocol == "grpc"
    assert config.cache_write_attribute == "gen_ai.usage.cache_write.input_tokens"
