"""Enumerations shared by the record model and the database schema."""

from __future__ import annotations

from enum import StrEnum


class TokenSource(StrEnum):
    """Where a record's token counts came from.

    Analytics should treat anything other than :attr:`PROVIDER` as an estimate.
    """

    PROVIDER = "provider"
    TOKENIZER = "tokenizer"
    HEURISTIC = "heuristic"


class CallType(StrEnum):
    """What kind of model call produced a record."""

    COMPLETION = "completion"
    TOOL = "tool"
    EMBEDDING = "embedding"
