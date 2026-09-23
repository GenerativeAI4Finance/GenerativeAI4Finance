"""Token counting and the precedence of caller-supplied counts."""

from __future__ import annotations

import tokenmeter
from conftest import Harness
from tokenmeter import TokenSource
from tokenmeter.counting import TokenCounter
from tokenmeter.otel import attributes as attrs


def test_openai_uses_a_real_tokenizer() -> None:
    result = TokenCounter(4.0).count("hello world, this is a test", "openai", "gpt-4o")
    assert result.source is TokenSource.TOKENIZER
    assert result.tokens == 7


def test_anthropic_falls_back_to_the_heuristic() -> None:
    result = TokenCounter(4.0).count("abcdefgh", "anthropic", "claude-opus-5")
    assert result.source is TokenSource.HEURISTIC
    assert result.tokens == 2


def test_empty_text_counts_zero_without_claiming_provider_accuracy() -> None:
    result = TokenCounter(4.0).count(None, "anthropic", "claude-opus-5")
    assert result.tokens == 0
    assert result.source is TokenSource.HEURISTIC


def test_explicit_counts_win_and_are_marked_provider(meter: Harness) -> None:
    tokenmeter.track(
        "ignored",
        "ignored",
        model="claude-opus-5",
        provider="anthropic",
        input_tokens=1234,
        output_tokens=56,
    )
    span = meter.only_span()
    assert span.attributes[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 1234
    assert span.attributes[attrs.GEN_AI_USAGE_OUTPUT_TOKENS] == 56
    assert span.attributes[attrs.TOKENMETER_TOKEN_SOURCE] == TokenSource.PROVIDER.value


def test_partial_override_reports_the_weaker_source(meter: Harness) -> None:
    tokenmeter.track(
        "abcdefgh",
        "response text",
        model="claude-opus-5",
        provider="anthropic",
        input_tokens=1000,
    )
    span = meter.only_span()
    assert span.attributes[attrs.GEN_AI_USAGE_INPUT_TOKENS] == 1000
    assert span.attributes[attrs.TOKENMETER_TOKEN_SOURCE] == TokenSource.HEURISTIC.value
