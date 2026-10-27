"""A provider-neutral, citation-checked EDD finding extraction layer.

The built-in extractor only emits verbatim source claims. Optional providers
can propose additional candidate types, but all candidates must include an
exact quote and character offsets from a supplied source document.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Iterable, Literal, Mapping, Protocol, Sequence


StatementType = Literal[
    "source_claim", "extracted_fact", "model_inference", "unresolved"
]


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    text: str
    title: str = ""
    reference: str | None = None
    url: str | None = None
    evidence_id: str | None = None
    claim_reference: str | None = None
    finding_reference: str | None = None
    source_type: str | None = None

    @classmethod
    def from_edd001_record(cls, record: Mapping, text: str) -> "SourceDocument":
        """Adapt an EDD-001 compact source record plus its supplied source text."""
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("EDD-001 source record needs a non-empty source_id.")
        title = record.get("description")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("EDD-001 source record needs a non-empty description.")
        if not isinstance(text, str):
            raise TypeError("Source text must be a string.")
        return cls(
            source_id=source_id,
            title=title,
            url=record.get("url"),
            source_type=record.get("source_type"),
            text=text,
        )

    @classmethod
    def from_edd002_record(cls, record: Mapping, text: str) -> "SourceDocument":
        """Adapt an EDD-002 evidence record plus its supplied source text.

        The excerpt/summary field is not substituted for source text: callers
        must provide the actual retrieved passage or document text separately.
        """
        evidence_id = record.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.strip():
            raise ValueError("EDD-002 evidence record needs a non-empty evidence_id.")
        claim_reference = record.get("claim_reference")
        title = record.get("title")
        if not isinstance(claim_reference, str) or not claim_reference.strip():
            raise ValueError("EDD-002 evidence record needs a non-empty claim_reference.")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("EDD-002 evidence record needs a non-empty title.")
        if not isinstance(text, str):
            raise TypeError("Source text must be a string.")
        return cls(
            source_id=evidence_id,
            text=text,
            title=title,
            reference=record.get("reference"),
            url=record.get("url"),
            evidence_id=evidence_id,
            claim_reference=claim_reference,
            finding_reference=record.get("finding_reference"),
            source_type=record.get("source_type"),
        )


@dataclass(frozen=True)
class CandidateFinding:
    statement: str
    statement_type: StatementType
    source_id: str
    quote: str
    start_char: int
    end_char: int
    note: str | None = None


@dataclass
class Finding:
    finding_id: str
    statement: str
    statement_type: StatementType
    source_reference: dict
    evidence: dict
    review_status: str
    reviewer_note: str | None = None


@dataclass
class RejectedCandidate:
    candidate: dict
    code: str
    reason: str


@dataclass
class ExtractionResult:
    status: str
    findings: list[Finding] = field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = field(default_factory=list)
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "findings": [asdict(item) for item in self.findings],
            "rejected_candidates": [asdict(item) for item in self.rejected_candidates],
            "message": self.message,
        }


class CandidateProvider(Protocol):
    """Optional model/provider adapter. Implementations return raw candidates."""

    def generate_candidates(
        self, sources: Sequence[SourceDocument]
    ) -> Iterable[CandidateFinding | dict]:
        """Propose candidate findings; provider output is never trusted directly."""


def _candidate_dict(candidate: CandidateFinding | dict) -> dict:
    if isinstance(candidate, CandidateFinding):
        return asdict(candidate)
    if isinstance(candidate, dict):
        return candidate
    return {"value": repr(candidate)}


def _validate_one(
    raw: CandidateFinding | dict,
    source_by_id: dict[str, SourceDocument],
    index: int,
) -> Finding | RejectedCandidate:
    data = _candidate_dict(raw)
    required = {
        "statement", "statement_type", "source_id", "quote", "start_char", "end_char"
    }
    missing = sorted(required - data.keys())
    if missing:
        return RejectedCandidate(data, "missing_fields", f"Candidate is missing required fields: {', '.join(missing)}.")

    source_id = data.get("source_id")
    source = source_by_id.get(source_id) if isinstance(source_id, str) else None
    if source is None:
        return RejectedCandidate(data, "unknown_source", "Candidate does not reference a supplied source record.")

    statement_type = data.get("statement_type")
    allowed_types = {"source_claim", "extracted_fact", "model_inference", "unresolved"}
    if not isinstance(statement_type, str) or statement_type not in allowed_types:
        return RejectedCandidate(data, "invalid_statement_type", "Candidate has an unsupported statement_type label.")

    statement, quote = data.get("statement"), data.get("quote")
    start, end = data.get("start_char"), data.get("end_char")
    if not isinstance(statement, str) or not statement.strip():
        return RejectedCandidate(data, "empty_statement", "Candidate statement must be a non-empty string.")
    if not isinstance(quote, str) or not quote:
        return RejectedCandidate(data, "missing_quote", "Candidate must include a non-empty supporting passage.")
    if data.get("note") is not None and not isinstance(data.get("note"), str):
        return RejectedCandidate(data, "invalid_note", "Optional candidate note must be a string or null.")
    if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int):
        return RejectedCandidate(data, "invalid_location", "Source location must use integer start_char and end_char offsets.")
    if start < 0 or end <= start or end > len(source.text):
        return RejectedCandidate(data, "invalid_location", "Source character offsets are outside the supplied text.")
    if source.text[start:end] != quote:
        return RejectedCandidate(data, "quote_mismatch", "Quoted passage does not exactly match the referenced source and offsets.")

    # Source claims preserve the exact wording. A normalized/structured fact
    # may differ from the passage, but must be explicitly sent for review.
    if statement_type == "source_claim" and statement != quote:
        return RejectedCandidate(
            data,
            "unsupported_paraphrase",
            "Source-claim candidates must preserve the exact source passage; paraphrases need another label.",
        )

    if statement_type == "model_inference":
        review_status = "requires_human_review"
        reviewer_note = "Model inference is a hypothesis, not a verified fact; review it against the cited passage and other evidence."
    elif statement_type == "unresolved":
        review_status = "requires_human_review"
        reviewer_note = data.get("note") or "The source passage leaves the question unresolved; human review is required."
    elif statement_type == "extracted_fact" and statement != quote:
        review_status = "requires_human_review"
        reviewer_note = data.get("note") or "Structured extraction differs from the verbatim passage; verify the value and interpretation against the source."
    else:
        review_status = "source_backed_candidate"
        reviewer_note = data.get("note")

    return Finding(
        finding_id=f"CAND-{index:04d}",
        statement=statement,
        statement_type=statement_type,
        source_reference={
            "source_id": source.source_id,
            "evidence_id": source.evidence_id,
            "claim_reference": source.claim_reference,
            "finding_reference": source.finding_reference,
            "source_type": source.source_type,
            "title": source.title,
            "reference": source.reference,
            "url": source.url,
        },
        evidence={"quote": quote, "start_char": start, "end_char": end},
        review_status=review_status,
        reviewer_note=reviewer_note,
    )


def validate_candidates(
    sources: Sequence[SourceDocument],
    candidates: Iterable[CandidateFinding | dict],
) -> ExtractionResult:
    """Validate provider candidates and retain only traceable, passage-backed items."""
    source_by_id: dict[str, SourceDocument] = {}
    for source in sources:
        if not isinstance(source.source_id, str) or not source.source_id.strip() or source.source_id in source_by_id:
            raise ValueError("Source IDs must be non-empty and unique.")
        if not isinstance(source.text, str):
            raise TypeError("Source text must be a string.")
        if (
            not isinstance(source.title, str)
            or (source.reference is not None and not isinstance(source.reference, str))
            or (source.url is not None and not isinstance(source.url, str))
            or (source.evidence_id is not None and not isinstance(source.evidence_id, str))
            or (source.claim_reference is not None and not isinstance(source.claim_reference, str))
            or (source.finding_reference is not None and not isinstance(source.finding_reference, str))
            or (source.source_type is not None and not isinstance(source.source_type, str))
        ):
            raise TypeError("Source metadata must use strings or null for optional reference fields.")
        source_by_id[source.source_id] = source

    findings: list[Finding] = []
    rejected: list[RejectedCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        validated = _validate_one(candidate, source_by_id, index)
        if isinstance(validated, RejectedCandidate):
            rejected.append(validated)
        else:
            findings.append(validated)

    if not findings:
        message = (
            "Insufficient evidence: no candidate was supported by an exact passage "
            "from a supplied source record."
        )
        return ExtractionResult("insufficient_evidence", findings, rejected, message)
    if any(item.review_status == "requires_human_review" for item in findings):
        return ExtractionResult(
            "human_review_required", findings, rejected,
            "Model inferences or unresolved items were returned; human review is required before use.",
        )
    return ExtractionResult("candidates_extracted", findings, rejected)


def _verbatim_candidates(sources: Sequence[SourceDocument]) -> list[CandidateFinding]:
    """Split source text into verbatim sentence/line candidates with exact offsets."""
    candidates: list[CandidateFinding] = []
    for source in sources:
        # Split after sentence punctuation followed by whitespace, or on lines;
        # retain original offsets and do not normalize the evidence text.
        for match in re.finditer(r"[^\r\n]+", source.text):
            line_start, _ = match.span()
            line = match.group()
            for sentence_match in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", line):
                raw = sentence_match.group()
                left_trim = len(raw) - len(raw.lstrip())
                right_trimmed = raw.rstrip()
                if not right_trimmed:
                    continue
                start = line_start + sentence_match.start() + left_trim
                end = line_start + sentence_match.start() + len(right_trimmed)
                quote = source.text[start:end]
                if not quote.strip():
                    continue
                candidates.append(CandidateFinding(
                    statement=quote,
                    statement_type="source_claim",
                    source_id=source.source_id,
                    quote=quote,
                    start_char=start,
                    end_char=end,
                ))
    return candidates


def extract_findings(
    sources: Sequence[SourceDocument],
    provider: CandidateProvider | None = None,
) -> ExtractionResult:
    """Extract candidates from supplied sources and validate every citation.

    Without a provider, returns only verbatim source claims. Provider-generated
    candidates are treated as untrusted and pass through the same strict checks.
    """
    for source in sources:
        if not isinstance(source.source_id, str) or not source.source_id.strip() or not isinstance(source.text, str):
            raise ValueError("Each source needs a non-empty source_id and string text.")
    candidates = (
        provider.generate_candidates(sources)
        if provider is not None
        else _verbatim_candidates(sources)
    )
    return validate_candidates(sources, candidates)
