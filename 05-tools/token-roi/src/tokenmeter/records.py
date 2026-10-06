"""The canonical usage record and the normalised shape adapters produce."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tokenmeter.enums import CallType, TokenSource


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class UsageSample(BaseModel):
    """Token usage for a single model call, without any prompt or response text.

    Adapters normalise agent-SDK objects into this shape; the client stamps the
    remaining fields to produce a :class:`TokenUsageRecord`.
    """

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    token_source: TokenSource = TokenSource.PROVIDER
    call_type: CallType = CallType.COMPLETION
    duration_ms: float | None = Field(default=None, ge=0)
    run_id: str | None = None
    agent_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenUsageRecord(BaseModel):
    """One row of ``token_usage``. Mirrors the table one-to-one."""

    model_config = ConfigDict(frozen=True, protected_namespaces=())

    #: When the model call *completed*; the span is back-dated by ``duration_ms``.
    timestamp: datetime = Field(default_factory=_utc_now)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    token_source: TokenSource
    call_type: CallType = CallType.COMPLETION
    duration_ms: float | None = Field(default=None, ge=0)
    run_id: str | None = None
    agent_name: str | None = None
    environment: str | None = None
    app_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
