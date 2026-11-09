import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "financial_event.schema.json").read_text(encoding="utf-8"))
ROWS = json.loads((ROOT / "examples" / "synthetic_records.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def test_schema_and_synthetic_examples_are_valid():
    Draft202012Validator.check_schema(SCHEMA)
    assert len(ROWS) == 3
    assert all(row["synthetic"] for row in ROWS)
    for row in ROWS:
        VALIDATOR.validate(row)


def test_feature_block_rejects_future_target_fields():
    row = copy.deepcopy(ROWS[0])
    row["features_at_t"]["values"]["default_within_horizon"] = {"value": False, "missing": False}
    assert any("Additional properties" in error.message for error in VALIDATOR.iter_errors(row))


def test_missing_feature_requires_null_value_and_missing_flag():
    row = copy.deepcopy(ROWS[0])
    row["features_at_t"]["values"]["monthly_revenue_usd"] = {"value": None, "missing": False}
    assert list(VALIDATOR.iter_errors(row))


def test_pending_outcome_cannot_contain_a_realized_label():
    row = copy.deepcopy(ROWS[2])
    row["outcomes_after_t"]["values"]["default_within_horizon"] = {"value": False, "missing": False}
    assert list(VALIDATOR.iter_errors(row))


def test_example_timestamps_respect_prediction_cutoff_and_horizon():
    for row in ROWS:
        prediction_time = datetime.fromisoformat(row["prediction_time_utc"].replace("Z", "+00:00"))
        feature_time = datetime.fromisoformat(row["features_at_t"]["as_of_utc"].replace("Z", "+00:00"))
        assert feature_time <= prediction_time
        if row["event_timestamp_utc"] is not None:
            event_time = datetime.fromisoformat(row["event_timestamp_utc"].replace("Z", "+00:00"))
            assert event_time <= prediction_time
        outcome_time = row["outcomes_after_t"]["observed_at_utc"]
        if outcome_time is not None:
            outcome_time = datetime.fromisoformat(outcome_time.replace("Z", "+00:00"))
            assert prediction_time < outcome_time <= prediction_time + timedelta(days=row["target_horizon_days"])
