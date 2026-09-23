"""Attribute names and value mappings for the GenAI semantic conventions.

The names are hardcoded here rather than imported from
``opentelemetry.semantic_conventions._incubating`` for two reasons: that module is
explicitly unstable, and it currently disagrees with the published registry about
the cache-write attribute (it exports ``gen_ai.usage.cache_creation.input_tokens``
where the spec says ``gen_ai.usage.cache_write.input_tokens``). Keeping our own
constants means one file to update when the conventions settle.

Source: https://github.com/open-telemetry/semantic-conventions-genai
"""

from __future__ import annotations

from tokenmeter.enums import CallType

# --- Standard GenAI attributes ---------------------------------------------------
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_TOKEN_TYPE = "gen_ai.token.type"
GEN_AI_CONVERSATION_ID = "gen_ai.conversation.id"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"

#: Current spec name. The older ``gen_ai.usage.cache_creation.input_tokens`` is
#: still emitted by some tooling; switch with ``OtelConfig.cache_write_attribute``.
GEN_AI_USAGE_CACHE_WRITE_INPUT_TOKENS = "gen_ai.usage.cache_write.input_tokens"
GEN_AI_USAGE_CACHE_CREATION_INPUT_TOKENS = "gen_ai.usage.cache_creation.input_tokens"

# --- Standard metric names -------------------------------------------------------
METRIC_TOKEN_USAGE = "gen_ai.client.token.usage"
UNIT_TOKEN = "{token}"

# --- Non-standard, tokenmeter-specific -------------------------------------------
# The GenAI conventions define no monetary attribute, so these are our own. They are
# namespaced so a strictly conformant backend ignores rather than misreads them.
GEN_AI_USAGE_COST = "gen_ai.usage.cost"
GEN_AI_USAGE_COST_CURRENCY = "gen_ai.usage.cost.currency"
METRIC_TOKEN_COST = "gen_ai.client.token.cost"
UNIT_COST = "{USD}"

TOKENMETER_TOKEN_SOURCE = "tokenmeter.token_source"
TOKENMETER_ENVIRONMENT = "tokenmeter.environment"
TOKENMETER_APP_VERSION = "tokenmeter.app_version"
TOKENMETER_METADATA_PREFIX = "tokenmeter.metadata."

# --- Value mappings --------------------------------------------------------------
TOKEN_TYPE_INPUT = "input"
TOKEN_TYPE_OUTPUT = "output"

#: Maps our provider strings onto ``gen_ai.provider.name`` well-known values.
PROVIDER_NAMES: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "azure_openai": "azure.ai.openai",
    "azure-openai": "azure.ai.openai",
    "bedrock": "aws.bedrock",
    "foundry": "azure.ai.inference",
    "google": "gcp.gen_ai",
    "gemini": "gcp.gemini",
    "vertex": "gcp.vertex_ai",
}

#: Maps our call types onto ``gen_ai.operation.name`` well-known values.
OPERATION_NAMES: dict[CallType, str] = {
    CallType.COMPLETION: "chat",
    CallType.EMBEDDING: "embeddings",
    CallType.TOOL: "execute_tool",
}


def provider_name(provider: str) -> str:
    """Map a provider string to its convention value.

    ``gen_ai.provider.name`` is an open enum, so an unmapped provider passes
    through verbatim rather than being dropped.
    """
    return PROVIDER_NAMES.get(provider.strip().lower(), provider.strip().lower())


def operation_name(call_type: CallType) -> str:
    """Map a call type to its ``gen_ai.operation.name`` value."""
    return OPERATION_NAMES[call_type]
