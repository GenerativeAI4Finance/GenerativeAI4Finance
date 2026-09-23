"""Agent-SDK adapters: parsing usage and the instrument dispatcher."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

import tokenmeter
from conftest import Harness
from tokenmeter import TokenSource, UnknownAdapterError
from tokenmeter.adapters import claude_agent, google_adk, openai_agents
from tokenmeter.otel import attributes as attrs


class FakeAgent(BaseModel):
    """Stands in for an OpenAI Agents ``Agent``."""

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    name: str
    model: str


class FakeResponse(BaseModel):
    """Stands in for a ``ModelResponse``."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    usage: Any


class FakeRunResult(BaseModel):
    """Stands in for a ``RunResult``."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    raw_responses: list[FakeResponse]
    last_agent: FakeAgent


def test_claude_result_message_yields_one_sample_per_model() -> None:
    types = pytest.importorskip("claude_agent_sdk.types")
    result = types.ResultMessage(
        subtype="success",
        duration_ms=10,
        duration_api_ms=8,
        is_error=False,
        num_turns=1,
        session_id="sess-1",
        model_usage={
            "claude-opus-5": {
                "inputTokens": 10,
                "outputTokens": 5,
                "cacheReadInputTokens": 3,
                "cacheCreationInputTokens": 2,
                "webSearchRequests": 0,
                "costUSD": 0.1,
                "contextWindow": 1000,
                "maxOutputTokens": 100,
                "provider": "firstParty",
            }
        },
    )
    (sample,) = claude_agent.samples_from_result(result)
    assert sample.provider == "anthropic"
    assert sample.model == "claude-opus-5"
    assert (sample.input_tokens, sample.output_tokens) == (10, 5)
    assert (sample.cache_read_tokens, sample.cache_write_tokens) == (3, 2)
    assert sample.run_id == "sess-1"
    assert sample.token_source is TokenSource.PROVIDER


def test_claude_platform_label_maps_to_a_billing_provider() -> None:
    types = pytest.importorskip("claude_agent_sdk.types")
    result = types.ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="s",
        model_usage={
            "claude-opus-5": {
                "inputTokens": 1,
                "outputTokens": 1,
                "cacheReadInputTokens": 0,
                "cacheCreationInputTokens": 0,
                "webSearchRequests": 0,
                "costUSD": 0.0,
                "contextWindow": 1,
                "maxOutputTokens": 1,
                "provider": "bedrock",
            }
        },
    )
    assert claude_agent.samples_from_result(result)[0].provider == "bedrock"


def test_claude_assistant_message_without_usage_is_skipped() -> None:
    types = pytest.importorskip("claude_agent_sdk.types")
    message = types.AssistantMessage(content=[], model="claude-opus-5")
    assert claude_agent.sample_from_assistant_message(message) is None


def test_claude_instrument_patches_and_restores_query() -> None:
    sdk = pytest.importorskip("claude_agent_sdk")
    original = sdk.query
    claude_agent.instrument()
    try:
        assert sdk.query is not original
    finally:
        claude_agent.uninstrument()
    assert sdk.query is original


def test_openai_cached_tokens_are_subtracted_from_input() -> None:
    usage_module = pytest.importorskip("agents.usage")
    usage = usage_module.Usage(requests=1, input_tokens=1000, output_tokens=50, total_tokens=1050)
    usage.input_tokens_details.cached_tokens = 800
    sample = openai_agents.sample_from_usage(usage, "gpt-4o")
    assert sample is not None
    assert sample.input_tokens == 200
    assert sample.cache_read_tokens == 800
    assert sample.provider == "openai"


def test_openai_run_result_yields_one_sample_per_response() -> None:
    usage_module = pytest.importorskip("agents.usage")
    usage = usage_module.Usage(requests=1, input_tokens=100, output_tokens=10, total_tokens=110)
    result = FakeRunResult(
        raw_responses=[FakeResponse(usage=usage), FakeResponse(usage=usage)],
        last_agent=FakeAgent(name="researcher", model="gpt-4o"),
    )
    samples = openai_agents.samples_from_run_result(result)
    assert len(samples) == 2
    assert {sample.agent_name for sample in samples} == {"researcher"}
    assert {sample.model for sample in samples} == {"gpt-4o"}


def test_google_event_folds_thinking_into_output_and_strips_cached_input() -> None:
    pytest.importorskip("google.adk")
    events = pytest.importorskip("google.adk.events")
    genai_types = pytest.importorskip("google.genai.types")
    event = events.Event(
        author="planner",
        invocation_id="inv-1",
        model_version="gemini-2.5-pro",
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1000,
            cached_content_token_count=600,
            candidates_token_count=120,
            thoughts_token_count=30,
            tool_use_prompt_token_count=10,
        ),
    )
    sample = google_adk.sample_from_event(event)
    assert sample is not None
    assert sample.input_tokens == 410
    assert sample.output_tokens == 150
    assert sample.cache_read_tokens == 600
    assert (sample.run_id, sample.agent_name) == ("inv-1", "planner")


def test_google_partial_events_are_ignored() -> None:
    events = pytest.importorskip("google.adk.events")
    genai_types = pytest.importorskip("google.genai.types")
    event = events.Event(
        author="planner",
        partial=True,
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(prompt_token_count=5),
    )
    assert google_adk.sample_from_event(event) is None


def test_unknown_adapter_name_fails_loudly() -> None:
    with pytest.raises(UnknownAdapterError, match="claude_agent"):
        tokenmeter.instrument("not_a_real_sdk")


def test_adapter_samples_reach_the_sink(meter: Harness) -> None:
    events = pytest.importorskip("google.adk.events")
    genai_types = pytest.importorskip("google.genai.types")
    event = events.Event(
        author="planner",
        invocation_id="inv-2",
        model_version="gemini-2.5-pro",
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20
        ),
    )
    assert google_adk.track_event(event) is True
    span = meter.only_span()
    assert span.attributes[attrs.GEN_AI_PROVIDER_NAME] == "gcp.gen_ai"
    assert span.attributes[attrs.GEN_AI_CONVERSATION_ID] == "inv-2"


def test_instrument_round_trip_leaves_the_sdks_untouched() -> None:
    runners = pytest.importorskip("google.adk.runners")
    original = runners.Runner.run_async
    tokenmeter.instrument("google_adk")
    try:
        assert runners.Runner.run_async is not original
    finally:
        tokenmeter.uninstrument("google_adk")
    assert runners.Runner.run_async is original
