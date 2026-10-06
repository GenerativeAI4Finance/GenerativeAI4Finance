"""The price book: in-memory lookup and per-record cost computation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from tokenmeter.config import ModelCost
from tokenmeter.records import TokenUsageRecord

logger = logging.getLogger("tokenmeter")

TOKENS_PER_MILLION = Decimal(1_000_000)
DEFAULT_CURRENCY = "USD"


class CostBreakdown(BaseModel):
    """What one record cost, split by the rate that produced each part."""

    model_config = ConfigDict(frozen=True)

    input_cost: Decimal
    output_cost: Decimal
    cache_write_cost: Decimal
    cache_read_cost: Decimal
    total_cost: Decimal
    currency: str = DEFAULT_CURRENCY


class PriceBook:
    """Normalised prices for the configured ``(provider, model)`` pairs."""

    def __init__(self, costs: Sequence[ModelCost]) -> None:
        self._by_key: dict[tuple[str, str], ModelCost] = {cost.key: cost for cost in costs}
        self._warned: set[tuple[str, str]] = set()

    def get(self, provider: str, model: str) -> ModelCost | None:
        """Return the configured price for a pair, or ``None`` if it is unknown."""
        return self._by_key.get((provider.strip().lower(), model.strip().lower()))

    def warn_if_unknown(self, provider: str, model: str) -> None:
        """Log one warning the first time an unpriced pair is seen."""
        key = (provider.strip().lower(), model.strip().lower())
        if key in self._by_key or key in self._warned:
            return
        self._warned.add(key)
        logger.warning(
            "tokenmeter: no configured cost for provider=%r model=%r; "
            "usage is still emitted but carries no cost attribute",
            key[0],
            key[1],
        )

    def cost_for(self, record: TokenUsageRecord) -> CostBreakdown | None:
        """Cost a record, or return ``None`` when its pair has no configured price."""
        price = self.get(record.provider, record.model)
        if price is None:
            return None
        input_cost = _rate_cost(record.input_tokens, price.input_cost_per_1m)
        output_cost = _rate_cost(record.output_tokens, price.output_cost_per_1m)
        cache_write_cost = _rate_cost(record.cache_write_tokens, price.cache_write_cost_per_1m)
        cache_read_cost = _rate_cost(record.cache_read_tokens, price.cache_read_cost_per_1m)
        return CostBreakdown(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_write_cost=cache_write_cost,
            cache_read_cost=cache_read_cost,
            total_cost=input_cost + output_cost + cache_write_cost + cache_read_cost,
        )


def _rate_cost(tokens: int, rate_per_million: Decimal) -> Decimal:
    """Cost of ``tokens`` at a per-million-token rate."""
    return (Decimal(tokens) / TOKENS_PER_MILLION) * rate_per_million
