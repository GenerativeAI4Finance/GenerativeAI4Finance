"""Exception hierarchy for tokenmeter.

These are raised only from configuration-time entry points (``init``,
``instrument``). The hot path (``track``) never raises into caller code.
"""

from __future__ import annotations


class TokenMeterError(Exception):
    """Base class for every error raised by tokenmeter."""


class NotInitializedError(TokenMeterError):
    """Raised when the library is used before :func:`tokenmeter.init`."""


class AlreadyInitializedError(TokenMeterError):
    """Raised when :func:`tokenmeter.init` is called twice without shutdown."""


class AdapterUnavailableError(TokenMeterError):
    """Raised when an agent-SDK adapter is requested but its SDK is not installed."""


class UnknownAdapterError(TokenMeterError):
    """Raised when :func:`tokenmeter.instrument` is given an unrecognised adapter name."""


class ExporterUnavailableError(TokenMeterError):
    """Raised when OTLP export is requested but the exporter package is not installed."""
