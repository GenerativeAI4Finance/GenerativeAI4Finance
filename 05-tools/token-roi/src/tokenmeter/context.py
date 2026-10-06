"""Correlation context.

``run_context`` sets the run id and agent name for everything executed inside it.
It is backed by :mod:`contextvars`, so the values propagate into asyncio tasks and
therefore into nested agent-SDK calls without threading arguments through.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, ConfigDict

_run_id: ContextVar[str | None] = ContextVar("tokenmeter_run_id", default=None)
_agent_name: ContextVar[str | None] = ContextVar("tokenmeter_agent_name", default=None)


class Correlation(BaseModel):
    """The correlation values currently in scope."""

    model_config = ConfigDict(frozen=True)

    run_id: str | None = None
    agent_name: str | None = None


def current_correlation() -> Correlation:
    """Return the correlation values in scope on this task or thread."""
    return Correlation(run_id=_run_id.get(), agent_name=_agent_name.get())


@contextmanager
def run_context(run_id: str | None = None, agent_name: str | None = None) -> Iterator[Correlation]:
    """Scope a run id and agent name to the enclosed block.

    A run id is generated when one is not supplied, so every agent run is grouped
    even if the caller does not track ids itself.
    """
    correlation = Correlation(run_id=run_id or uuid.uuid4().hex, agent_name=agent_name)
    run_token = _run_id.set(correlation.run_id)
    agent_token = _agent_name.set(correlation.agent_name)
    try:
        yield correlation
    finally:
        _run_id.reset(run_token)
        _agent_name.reset(agent_token)
