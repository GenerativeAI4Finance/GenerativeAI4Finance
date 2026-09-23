"""Dispatch for turning agent-SDK auto-instrumentation on and off."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType

from tokenmeter.errors import AdapterUnavailableError, UnknownAdapterError

logger = logging.getLogger("tokenmeter")

ADAPTER_MODULES: dict[str, str] = {
    "claude_agent": "tokenmeter.adapters.claude_agent",
    "openai_agents": "tokenmeter.adapters.openai_agents",
    "google_adk": "tokenmeter.adapters.google_adk",
}


def instrument(*names: str) -> None:
    """Auto-record usage from the named agent SDKs.

    Valid names are the keys of :data:`ADAPTER_MODULES`. Naming an SDK that is not
    installed raises :class:`~tokenmeter.errors.AdapterUnavailableError`, so a typo
    or a missing dependency fails loudly. Passing no names instruments every SDK
    that happens to be installed and skips the rest.
    """
    for name in names or tuple(ADAPTER_MODULES):
        _apply(name, action="instrument", required=bool(names))


def uninstrument(*names: str) -> None:
    """Undo :func:`instrument` for the named SDKs, or for all of them."""
    for name in names or tuple(ADAPTER_MODULES):
        _apply(name, action="uninstrument", required=bool(names))


def _apply(name: str, *, action: str, required: bool) -> None:
    """Run ``action`` on one adapter, tolerating a missing SDK when not required."""
    module = _load_adapter(name)
    try:
        getattr(module, action)()
    except AdapterUnavailableError:
        if required:
            raise
        logger.debug("tokenmeter: skipping %s adapter, its SDK is not installed", name)


def _load_adapter(name: str) -> ModuleType:
    """Import the adapter module registered under ``name``."""
    try:
        module_path = ADAPTER_MODULES[name]
    except KeyError:
        known = ", ".join(sorted(ADAPTER_MODULES))
        raise UnknownAdapterError(f"unknown adapter {name!r}; known adapters: {known}") from None
    return importlib.import_module(module_path)
