"""Source-backed candidate finding extraction for EDD review."""

from .extractor import (
    CandidateProvider,
    CandidateFinding,
    ExtractionResult,
    SourceDocument,
    extract_findings,
    validate_candidates,
)

__all__ = [
    "CandidateProvider",
    "CandidateFinding",
    "ExtractionResult",
    "SourceDocument",
    "extract_findings",
    "validate_candidates",
]
