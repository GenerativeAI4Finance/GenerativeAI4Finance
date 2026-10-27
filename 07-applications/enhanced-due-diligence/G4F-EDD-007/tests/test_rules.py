import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evidence_checks import (
    CheckConfig,
    observation_from_edd001,
    observation_from_edd002,
    observation_from_edd006,
    review_evidence,
)


def fixture():
    return json.loads((ROOT / "examples/synthetic_observations.json").read_text(encoding="utf-8"))


def test_synthetic_fixture_preserves_conflicting_company_values_and_flags_stale_records():
    data = fixture()
    result = review_evidence(data["observations"], as_of=data["as_of"])

    conflict = next(item for item in result["conflicts"] if item["attribute"] == "ownership_percentage")
    assert conflict["subject_id"] == "SYNTHETIC-COMPANY-001"
    assert {value["normalized_value"] for value in conflict["values"]} == {"6E+1", "4E+1"}
    assert sum(len(value["observations"]) for value in conflict["values"]) == 2
    assert conflict["resolution"] == "unresolved_requires_human_review"
    assert any(item["observation"]["observation_id"] == "OBS-ENTITY-003" for item in result["stale_evidence"])
    assert any(item["observation"]["subject_id"] == "SYNTHETIC-PERSON-001" for item in result["stale_evidence"])
    assert result["requires_human_review"] is True
    json.dumps(result)  # Output remains JSON-serializable for downstream EDD records.


def test_same_values_after_conservative_normalization_are_not_a_conflict():
    observations = [
        {"observation_id": "O-1", "subject_id": "ENTITY-1", "attribute": "status", "value": " Active ", "checked_date": "2026-10-20", "record_status": "available", "source_reference": {"source_id": "SRC-1"}},
        {"observation_id": "O-2", "subject_id": "ENTITY-1", "attribute": "status", "value": "active", "checked_date": "2026-10-21", "record_status": "available", "source_reference": {"source_id": "SRC-2"}},
        {"observation_id": "O-3", "subject_id": "ENTITY-1", "attribute": "ownership_percentage", "value": 60, "checked_date": "2026-10-21", "record_status": "available", "source_reference": {"source_id": "SRC-3"}},
        {"observation_id": "O-4", "subject_id": "ENTITY-1", "attribute": "ownership_percentage", "value": 60.0, "checked_date": "2026-10-21", "record_status": "available", "source_reference": {"source_id": "SRC-4"}},
    ]
    result = review_evidence(observations, as_of="2026-10-22")
    assert result["conflicts"] == []
    assert result["requires_human_review"] is False


def test_edd002_adapter_preserves_claim_and_finding_links_and_uses_access_date():
    record = {
        "evidence_id": "EDD-EV-007", "claim_reference": "CLAIM-007",
        "finding_reference": "F-007", "title": "Synthetic record",
        "access_date": "2026-10-20", "publication_date": "2020-01-01",
        "evidence_status": "available", "source_type": "official_record",
    }
    observation = observation_from_edd002(
        record, subject_id="SYNTHETIC-COMPANY-007",
        attribute="company_status", value="active",
    )
    result = review_evidence([observation], as_of="2026-10-27", config=CheckConfig(freshness_windows_days={"company_status": 7}))
    assert observation["checked_date"] == "2026-10-20"
    assert observation["source_reference"]["claim_reference"] == "CLAIM-007"
    assert observation["source_reference"]["finding_reference"] == "F-007"
    assert result["stale_evidence"] == []  # Exactly on the boundary is fresh.


def test_edd001_and_edd006_adapters_retain_source_and_exact_passage():
    from_001 = observation_from_edd001(
        {"source_id": "SRC-001", "source_type": "registry", "description": "Synthetic registry", "url": "https://example.org/synthetic"},
        subject_id="SYNTHETIC-COMPANY-001", attribute="company_status",
        value="active", checked_date="2026-10-20",
    )
    from_006 = observation_from_edd006(
        {"finding_id": "CAND-0001", "source_reference": {"source_id": "SRC-002", "evidence_id": "EDD-EV-002", "claim_reference": "CLAIM-002"}, "evidence": {"quote": "SYNTHETIC: Entity status is inactive.", "start_char": 0, "end_char": 38}},
        subject_id="SYNTHETIC-COMPANY-001", attribute="company_status",
        value="inactive", checked_date="2026-10-21",
    )
    result = review_evidence([from_001, from_006], as_of="2026-10-22")
    conflict = result["conflicts"][0]
    refs = [obs["source_reference"] for group in conflict["values"] for obs in group["observations"]]
    assert {ref.get("source_id") for ref in refs} == {"SRC-001", "SRC-002"}
    assert any(ref.get("supporting_passage", {}).get("quote") == "SYNTHETIC: Entity status is inactive." for ref in refs)
    assert any(ref.get("evidence_id") == "EDD-EV-002" for ref in refs)


def test_outdated_and_missing_check_dates_are_visible_and_require_review():
    observations = [
        {"observation_id": "O-1", "subject_id": "PERSON-SYNTHETIC-1", "attribute": "pep_screening", "value": "no_match", "checked_date": "2026-10-20", "record_status": "outdated", "source_reference": {"evidence_id": "EDD-EV-101"}},
        {"observation_id": "O-2", "subject_id": "PERSON-SYNTHETIC-2", "attribute": "pep_screening", "value": "no_match", "checked_date": None, "record_status": "available", "source_reference": {"source_id": "SRC-102"}},
        {"observation_id": "O-3", "subject_id": "PERSON-SYNTHETIC-3", "attribute": "sanctions_screening", "value": "potential_match", "checked_date": "2026-10-20", "record_status": "disputed", "source_reference": {"evidence_id": "EDD-EV-103"}},
    ]
    result = review_evidence(observations, as_of="2026-10-21")
    assert {item["reason"] for item in result["stale_evidence"]} == {"source_record_marked_outdated", "checked_date_unavailable"}
    assert {item["issue"] for item in result["evidence_status_issues"]} == {"outdated", "disputed"}
    assert result["requires_human_review"]


def test_expired_window_invalid_values_and_duplicate_ids_fail_clearly():
    record = {"observation_id": "O-1", "subject_id": "ENTITY-1", "attribute": "company_status", "value": "active", "checked_date": "2026-10-01", "record_status": "available", "source_reference": {"source_id": "SRC-1"}}
    result = review_evidence([record], as_of="2026-10-12", config=CheckConfig(freshness_windows_days={"company_status": 10}))
    assert result["stale_evidence"][0]["reason"] == "freshness_window_exceeded"
    with pytest.raises(ValueError, match="Duplicate observation_id"):
        review_evidence([record, record], as_of="2026-10-12")
    with pytest.raises(ValueError, match="valid YYYY-MM-DD"):
        review_evidence([record], as_of="27-10-2026")
    with pytest.raises(ValueError, match="non-null scalar"):
        review_evidence([{**record, "value": {"percent": 50}}], as_of="2026-10-12")


def test_config_mapping_rejects_unknown_keys_and_accepts_thresholds():
    config = CheckConfig.from_mapping({"default_max_age_days": 45, "freshness_windows_days": {"company_status": 10}})
    assert config.max_age_for("company_status") == 10
    assert config.max_age_for("other") == 45
    with pytest.raises(ValueError, match="Unknown configuration keys"):
        CheckConfig.from_mapping({"default_max_age_days": 45, "stale_days": 30})


def test_non_overlapping_case_local_subjects_do_not_conflict():
    observations = [
        {"observation_id": "O-1", "subject_id": "SYNTHETIC-PERSON-A", "attribute": "ownership_percentage", "value": 60, "checked_date": "2026-10-20", "record_status": "available", "source_reference": {"source_id": "SRC-A"}},
        {"observation_id": "O-2", "subject_id": "SYNTHETIC-PERSON-B", "attribute": "ownership_percentage", "value": 40, "checked_date": "2026-10-20", "record_status": "available", "source_reference": {"source_id": "SRC-B"}},
    ]
    assert review_evidence(observations, as_of="2026-10-21")["conflicts"] == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
