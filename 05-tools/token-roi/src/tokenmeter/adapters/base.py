"""Shared helpers for the agent-SDK adapters."""

from __future__ import annotations

import importlib
import logging
from collections.abc import Iterable, Mapping
from types import ModuleType
from typing import Any

from tokenmeter import api
from tokenmeter.errors import AdapterUnavailableError
from tokenmeter.records import UsageSample

logger = logging.getLogger("tokenmeter")


def emit(samples: Iterable[UsageSample]) -> int:
    """Record every sample and return how many were queued."""
    return sum(1 for sample in samples if api.record_sample(sample))


def require_module(module_name: str, install_hint: str) -> ModuleType:
    """Import an optional SDK, raising a clear error when it is missing."""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise AdapterUnavailableError(
            f"{module_name} is not installed; run `pip install {install_hint}` to use this adapter"
        ) from exc


def as_int(value: Any) -> int:
    """Coerce a usage field to a non-negative int, treating anything odd as zero."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    return max(0, int(value))


def field_of(source: Any, *names: str) -> Any:
    """Read the first present field from a mapping or object, by any of ``names``."""
    for name in names:
        if isinstance(source, Mapping):
            if name in source:
                return source[name]
        elif hasattr(source, name):
            return getattr(source, name)
    return None


def uncached_input(total_input_tokens: int, *cached_parts: int) -> int:
    """Return the input tokens billed at the full rate.

    Some providers (OpenAI, Google) report cached tokens as a *subset* of the
    prompt token count, while Anthropic reports them separately. tokenmeter
    stores ``input_tokens`` as the uncached remainder so one cost formula works
    across providers, so those subsets are subtracted here.
    """
    return max(0, total_input_tokens - sum(cached_parts))
