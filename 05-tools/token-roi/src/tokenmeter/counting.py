"""Local token counting.

Real tokenizers are used where one exists offline. For Anthropic and Google there
is no offline tokenizer — their accurate counts come from a network call — so text
is estimated with a character heuristic. Pass the provider's own usage numbers to
``track`` whenever you have them; the result is marked with its
:class:`~tokenmeter.enums.TokenSource` either way.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tokenmeter.enums import TokenSource

logger = logging.getLogger("tokenmeter")

_OPENAI_PROVIDERS = frozenset({"openai", "azure_openai", "azure-openai"})
_OPENAI_FALLBACK_ENCODING = "o200k_base"


class CountResult(BaseModel):
    """A token count and how it was derived."""

    model_config = ConfigDict(frozen=True)

    tokens: int = Field(ge=0)
    source: TokenSource


class TokenCounter:
    """Counts tokens for text, caching one tokenizer per ``(provider, model)`` pair."""

    def __init__(self, chars_per_token: float) -> None:
        self._chars_per_token = chars_per_token
        self._encodings: dict[tuple[str, str], Any | None] = {}

    def count(self, text: str | None, provider: str, model: str) -> CountResult:
        """Count the tokens in ``text`` for the given provider and model."""
        encoding = self._encoding_for(provider, model)
        if encoding is None:
            tokens = self._estimate(text) if text else 0
            return CountResult(tokens=tokens, source=TokenSource.HEURISTIC)
        tokens = len(encoding.encode(text)) if text else 0
        return CountResult(tokens=tokens, source=TokenSource.TOKENIZER)

    def _estimate(self, text: str) -> int:
        """Estimate tokens from character length."""
        return math.ceil(len(text) / self._chars_per_token)

    def _encoding_for(self, provider: str, model: str) -> Any | None:
        """Return a cached tokenizer for the pair, or ``None`` to use the heuristic."""
        key = (provider.strip().lower(), model.strip().lower())
        if key not in self._encodings:
            self._encodings[key] = _load_encoding(*key)
        return self._encodings[key]


def _load_encoding(provider: str, model: str) -> Any | None:
    """Resolve a tokenizer for one pair, or ``None`` when no offline tokenizer exists."""
    if provider not in _OPENAI_PROVIDERS:
        return None
    try:
        import tiktoken
    except ImportError:
        logger.info(
            "tokenmeter: tiktoken is not installed; falling back to heuristic counting "
            "for provider=%r. Install tokenmeter[tokenizers] for exact OpenAI counts.",
            provider,
        )
        return None
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding(_OPENAI_FALLBACK_ENCODING)
