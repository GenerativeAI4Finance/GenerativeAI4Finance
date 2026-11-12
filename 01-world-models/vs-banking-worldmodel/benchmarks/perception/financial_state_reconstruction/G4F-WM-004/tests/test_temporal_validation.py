import json
from pathlib import Path

from temporal_validation import validate_dataset


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "config" / "validation_rules.json"


def load_fixture(name):
    return json.loads((ROOT / "fixtures" / name).read_text(encoding="utf-8"))


def failed_checks(report):
    return {item["check_id"] for item in report["checks"] if item["status"] == "fail"}


def test_valid_fixture_passes_every_check():
    report = validate_dataset(load_fixture("valid_temporal_dataset.json"), RULES, generated_at_utc="2026-11-12T00:00:00Z")
    assert report["summary"] == {"status": "pass", "check_count": 9, "failed_check_count": 0, "issue_count": 0}


def test_invalid_fixture_triggers_expected_failures():
    report = validate_dataset(load_fixture("invalid_temporal_dataset.json"), RULES, generated_at_utc="2026-11-12T00:00:00Z")
    expected = {
        "duplicate_keys", "missing_timestamps", "impossible_transitions",
        "unit_consistency", "invalid_ranges", "future_data_leakage",
        "split_temporal_order", "split_entity_disjointness",
    }
    assert expected <= failed_checks(report)
    assert report["summary"]["status"] == "fail"
    assert report["summary"]["issue_count"] > 0


def test_future_feature_and_outcome_are_separately_diagnosed():
    payload = load_fixture("valid_temporal_dataset.json")
    record = payload["records"][0]
    record["features"]["balance_usd"]["available_at"] = "2025-02-01T00:00:00Z"
    record["outcome"]["observed_at"] = "2025-01-31T00:00:00Z"
    report = validate_dataset(payload, RULES, generated_at_utc="2026-11-12T00:00:00Z")
    leakage = next(check for check in report["checks"] if check["check_id"] == "future_data_leakage")
    assert {issue["code"] for issue in leakage["issues"]} >= {"feature_available_after_record_time", "outcome_not_future"}


def test_time_split_prevents_later_training_record():
    payload = load_fixture("valid_temporal_dataset.json")
    assignment = next(row for row in payload["splits"] if row["record_id"] == "R-006")
    assignment["split"] = "train"
    report = validate_dataset(payload, RULES, generated_at_utc="2026-11-12T00:00:00Z")
    assert "split_temporal_order" in failed_checks(report)


def test_report_has_machine_readable_check_details():
    report = validate_dataset(load_fixture("invalid_temporal_dataset.json"), RULES, generated_at_utc="2026-11-12T00:00:00Z")
    assert report["dataset_id"] == "WM004-SYNTHETIC-INVALID-FAILURES"
    assert all({"check_id", "status", "issue_count", "issues"} <= set(check) for check in report["checks"])
    assert all("code" in issue and "message" in issue for check in report["checks"] for issue in check["issues"])
