"""Cost computation and unknown-model handling."""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from conftest import OPUS_COST
from tokenmeter import TokenSource
from tokenmeter.pricing import PriceBook
from tokenmeter.records import TokenUsageRecord


def _record(**overrides: object) -> TokenUsageRecord:
    fields: dict[str, object] = {
        "provider": "anthropic",
        "model": "claude-opus-5",
        "input_tokens": 1000,
        "output_tokens": 100,
        "cache_read_tokens": 600,
        "cache_write_tokens": 200,
        "token_source": TokenSource.PROVIDER,
    }
    fields.update(overrides)
    return TokenUsageRecord(**fields)  # type: ignore[arg-type]


def test_cost_breakdown_matches_hand_computed_figure() -> None:
    cost = PriceBook([OPUS_COST]).cost_for(_record())
    assert cost is not None
    assert cost.input_cost == Decimal("0.005")
    assert cost.output_cost == Decimal("0.0025")
    assert cost.cache_write_cost == Decimal("0.00125")
    assert cost.cache_read_cost == Decimal("0.0003")
    assert cost.total_cost == Decimal("0.00905")
    assert cost.currency == "USD"


def test_unpriced_pair_has_no_cost() -> None:
    assert PriceBook([OPUS_COST]).cost_for(_record(provider="cohere", model="command")) is None


def test_unpriced_pair_warns_exactly_once(caplog: pytest.LogCaptureFixture) -> None:
    book = PriceBook([OPUS_COST])
    with caplog.at_level(logging.WARNING, logger="tokenmeter"):
        book.warn_if_unknown("cohere", "command")
        book.warn_if_unknown("cohere", "command")
    warnings = [r for r in caplog.records if "no configured cost" in r.message]
    assert len(warnings) == 1


def test_priced_pair_never_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="tokenmeter"):
        PriceBook([OPUS_COST]).warn_if_unknown("Anthropic", "Claude-Opus-5")
    assert caplog.records == []
