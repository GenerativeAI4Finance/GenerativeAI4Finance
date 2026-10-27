"""Detect contradictory values and evidence that exceeds freshness windows.

This module reports conditions for analyst review. It never chooses a winning
source or resolves a contradiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


EVIDENCE_STATUSES = {"available", "unavailable", "disputed", "outdated"}


@dataclass(frozen=True)
class CheckConfig:
    """Freshness windows in whole days, selected by attribute then default."""

    default_max_age_days: int = 180
    freshness_windows_days: Mapping[str, int] = field(default_factory=lambda: {
        "ownership_percentage": 365,
        "company_status": 90,
        "sanctions_screening": 30,
        "pep_screening": 30,
    })

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CheckConfig":
        """Load a config mapping while rejecting misspelled/unknown options."""
        if not isinstance(data, Mapping):
            raise TypeError("Configuration must be a mapping.")
        allowed = {"default_max_age_days", "freshness_windows_days"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"Unknown configuration keys: {', '.join(sorted(map(str, unknown)))}.")
        windows = data.get("freshness_windows_days", {
            "ownership_percentage": 365,
            "company_status": 90,
            "sanctions_screening": 30,
            "pep_screening": 30,
        })
        if not isinstance(windows, Mapping):
            raise ValueError("freshness_windows_days must be an object/map.")
        return cls(
            default_max_age_days=data.get("default_max_age_days", 180),
            freshness_windows_days=dict(windows),
        )

    def __post_init__(self) -> None:
        if isinstance(self.default_max_age_days, bool) or not isinstance(self.default_max_age_days, int) or self.default_max_age_days < 0:
            raise ValueError("default_max_age_days must be a non-negative integer.")
        for key, value in self.freshness_windows_days.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Freshness window names must be non-empty strings.")
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"Freshness window for {key!r} must be a non-negative integer.")

    def max_age_for(self, attribute: str) -> int:
        return self.freshness_windows_days.get(attribute, self.default_max_age_days)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _parse_date(value: Any, field_name: str, *, nullable: bool = False) -> date | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO date string" + (" or null." if nullable else "."))
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be a valid YYYY-MM-DD date.") from error
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.")
    return parsed


def _observation(
    observation_id: str,
    subject_id: str,
    attribute: str,
    value: Any,
    checked_date: str | None,
    record_status: str,
    source_reference: Mapping[str, Any],
) -> dict[str, Any]:
    _require_text(observation_id, "observation_id")
    _require_text(subject_id, "subject_id")
    _require_text(attribute, "attribute")
    if value is None or isinstance(value, (dict, list, tuple)):
        raise ValueError("value must be a non-null scalar so it can be compared explicitly.")
    if isinstance(value, float) and not (value == value and abs(value) != float("inf")):
        raise ValueError("value must not be NaN or infinite.")
    if isinstance(value, Decimal) and not value.is_finite():
        raise ValueError("value must not be NaN or infinite.")
    _parse_date(checked_date, "checked_date", nullable=True)
    if not isinstance(record_status, str) or record_status not in EVIDENCE_STATUSES:
        raise ValueError(f"record_status must be one of {sorted(EVIDENCE_STATUSES)}.")
    if not isinstance(source_reference, Mapping) or not any(
        isinstance(source_reference.get(key), str) and source_reference[key].strip()
        for key in ("source_id", "evidence_id")
    ):
        raise ValueError("source_reference must retain a non-empty source_id or evidence_id.")
    return {
        "observation_id": observation_id.strip(),
        "subject_id": subject_id.strip(),
        "attribute": attribute.strip(),
        "value": value,
        "checked_date": checked_date,
        "record_status": record_status,
        "source_reference": dict(source_reference),
    }


def observation_from_edd002(
    record: Mapping[str, Any], *, subject_id: str, attribute: str, value: Any,
    observation_id: str | None = None,
) -> dict[str, Any]:
    """Build a comparable observation from an EDD-002 evidence record.

    EDD-002's actual access date is used for freshness; publication date is not
    a substitute. `value` is an analyst-reviewed structured value, not parsed
    automatically from the excerpt or summary.
    """
    if not isinstance(record, Mapping):
        raise TypeError("EDD-002 record must be a mapping.")
    evidence_id = _require_text(record.get("evidence_id"), "evidence_id")
    claim_reference = _require_text(record.get("claim_reference"), "claim_reference")
    reference = {
        "evidence_id": evidence_id,
        "claim_reference": claim_reference,
        "finding_reference": record.get("finding_reference"),
        "source_type": record.get("source_type"),
        "title": record.get("title"),
        "reference": record.get("reference"),
        "url": record.get("url"),
    }
    return _observation(
        observation_id or evidence_id, subject_id, attribute, value,
        record.get("access_date"), record.get("evidence_status", "available"), reference,
    )


def observation_from_edd001(
    source_record: Mapping[str, Any], *, subject_id: str, attribute: str, value: Any,
    checked_date: str | None, observation_id: str | None = None,
    record_status: str = "available",
) -> dict[str, Any]:
    """Build an observation from an EDD-001 compact source record.

    EDD-001 source records do not contain a checked date, so callers must
    supply it from the case review context; it must not be inferred.
    """
    if not isinstance(source_record, Mapping):
        raise TypeError("EDD-001 source record must be a mapping.")
    source_id = _require_text(source_record.get("source_id"), "source_id")
    reference = {
        "source_id": source_id,
        "source_type": source_record.get("source_type"),
        "title": source_record.get("description"),
        "url": source_record.get("url"),
    }
    return _observation(
        observation_id or source_id, subject_id, attribute, value,
        checked_date, record_status, reference,
    )


def observation_from_edd006(
    finding: Mapping[str, Any], *, subject_id: str, attribute: str, value: Any,
    checked_date: str | None, observation_id: str | None = None,
    record_status: str = "available",
) -> dict[str, Any]:
    """Build an observation from an EDD-006 candidate after analyst review.

    EDD-006 citations identify the source and exact passage but do not carry a
    checked date. Supply the date from its linked source record. The extractor
    output itself is not treated as an independently verified fact.
    """
    if not isinstance(finding, Mapping):
        raise TypeError("EDD-006 finding must be a mapping.")
    source_reference = finding.get("source_reference")
    if not isinstance(source_reference, Mapping):
        raise ValueError("EDD-006 finding needs a source_reference.")
    evidence = finding.get("evidence")
    reference = dict(source_reference)
    if isinstance(evidence, Mapping):
        reference["supporting_passage"] = dict(evidence)
    candidate_id = finding.get("finding_id")
    if observation_id is None and isinstance(candidate_id, str):
        observation_id = candidate_id
    return _observation(
        observation_id or str(source_reference.get("source_id", "")),
        subject_id, attribute, value, checked_date, record_status, reference,
    )


def _normalized_value(value: Any) -> tuple[str, Any]:
    """Normalize only conservative scalar equivalences; preserve raw values."""
    if isinstance(value, bool):
        return "boolean", value
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value)).normalize()
        except InvalidOperation as error:
            raise ValueError("Numeric observation value is invalid.") from error
        return "number", str(number)
    if isinstance(value, str):
        return "text", value.strip().casefold()
    raise ValueError("value must be a string, boolean, or finite number.")


def review_evidence(
    observations: Sequence[Mapping[str, Any]], *, as_of: str,
    config: CheckConfig | None = None,
) -> dict[str, Any]:
    """Return conflict groups and stale evidence, preserving full source refs."""
    as_of_date = _parse_date(as_of, "as_of")
    assert as_of_date is not None
    config = config or CheckConfig()
    seen_ids: set[str] = set()
    checked: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    status_issues: list[dict[str, Any]] = []

    for raw in observations:
        if not isinstance(raw, Mapping):
            raise TypeError("Each observation must be a mapping.")
        item = _observation(
            raw.get("observation_id"), raw.get("subject_id"), raw.get("attribute"),
            raw.get("value"), raw.get("checked_date"), raw.get("record_status"),
            raw.get("source_reference"),
        )
        if item["observation_id"] in seen_ids:
            raise ValueError(f"Duplicate observation_id: {item['observation_id']}.")
        seen_ids.add(item["observation_id"])
        item["_normalized"] = _normalized_value(item["value"])
        checked_date = _parse_date(item["checked_date"], "checked_date", nullable=True)
        age_days = (as_of_date - checked_date).days if checked_date is not None else None
        max_age_days = config.max_age_for(item["attribute"])
        is_stale = item["record_status"] == "outdated" or (
            age_days is not None and age_days > max_age_days
        )
        if is_stale or checked_date is None:
            stale.append({
                "observation": {key: val for key, val in item.items() if key != "_normalized"},
                "age_days": age_days,
                "max_age_days": max_age_days,
                "reason": (
                    "source_record_marked_outdated" if item["record_status"] == "outdated"
                    else "checked_date_unavailable" if checked_date is None
                    else "freshness_window_exceeded"
                ),
            })
        if item["record_status"] in {"unavailable", "disputed", "outdated"}:
            status_issues.append({
                "observation": {key: val for key, val in item.items() if key != "_normalized"},
                "issue": item["record_status"],
                "requires_human_review": True,
            })
        checked.append(item)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in checked:
        grouped.setdefault((item["subject_id"], item["attribute"]), []).append(item)

    conflicts: list[dict[str, Any]] = []
    for (subject_id, attribute), group in sorted(grouped.items()):
        distinct: dict[tuple[str, Any], list[dict[str, Any]]] = {}
        for item in group:
            distinct.setdefault(item["_normalized"], []).append(item)
        if len(distinct) <= 1:
            continue
        values = []
        for (kind, normalized), records in sorted(distinct.items(), key=lambda pair: (pair[0][0], str(pair[0][1]))):
            values.append({
                "normalized_value": normalized,
                "value_type": kind,
                "observations": [
                    {key: val for key, val in record.items() if key != "_normalized"}
                    for record in records
                ],
            })
        conflicts.append({
            "subject_id": subject_id,
            "attribute": attribute,
            "values": values,
            "status": "conflicting_values",
            "resolution": "unresolved_requires_human_review",
            "requires_human_review": True,
        })

    return {
        "as_of": as_of,
        "conflicts": conflicts,
        "stale_evidence": stale,
        "evidence_status_issues": status_issues,
        "requires_human_review": bool(conflicts or stale or status_issues),
    }
