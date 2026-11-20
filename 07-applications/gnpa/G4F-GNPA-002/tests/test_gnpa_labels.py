import pandas as pd
import pytest

from synthetic_gnpa.generator import generate_synthetic_history
from synthetic_gnpa.labels import FEATURE_COLUMNS, TARGET_COLUMNS, label_observations
from synthetic_gnpa.validation import validate_history, validate_labeled_observations


def test_generator_is_deterministic_and_synthetic():
    first = generate_synthetic_history(n_borrowers=20, seed=7)
    second = generate_synthetic_history(n_borrowers=20, seed=7)
    pd.testing.assert_frame_equal(first, second)
    assert first["is_synthetic"].all()
    validate_history(first)


def test_time_dependent_labels_have_cures_and_censoring():
    history = generate_synthetic_history(n_borrowers=400, seed=20261120)
    labels = label_observations(history)
    assert (history["synthetic_asset_status"] == "npa").any()
    assert history["synthetic_cure_event"].any()
    assert labels["cure_within_90d"].eq(1).any()
    assert labels[TARGET_COLUMNS].isna().any().any()
    assert labels[TARGET_COLUMNS].eq(1).any().any()
    validate_labeled_observations(labels)


def test_features_do_not_contain_future_outcome_or_audit_fields():
    assert not (set(FEATURE_COLUMNS) & (set(TARGET_COLUMNS) | {
        "horizon_end_date", "outcome_observed_through", "censor_reason",
        "delinquency_event_date", "stress_event_date", "first_npa_effective_date",
        "cure_event_date",
    }))
    history = generate_synthetic_history(n_borrowers=12, seed=19)
    labels = label_observations(history)
    feature_rows = labels[FEATURE_COLUMNS]
    assert feature_rows["observation_date"].equals(labels["observation_date"])
    assert not any(col.startswith("future_") for col in feature_rows.columns)


def test_future_event_creates_positive_and_absent_incomplete_followup_is_null():
    history = generate_synthetic_history(n_borrowers=1, seed=1, n_snapshots=8)
    borrower = history["borrower_id"].iloc[0]
    history.loc[:, "synthetic_asset_status"] = "standard"
    history.loc[:, "days_past_due"] = 0
    history.loc[:, "npa_entry_event"] = False
    event_date = history.loc[history["snapshot_date"].eq(history["snapshot_date"].iloc[2]), "snapshot_date"].iloc[0]
    history.loc[history["snapshot_date"].eq(event_date), ["synthetic_asset_status", "days_past_due", "npa_entry_event"]] = ["npa", 120, True]
    history.loc[:, "observation_coverage_end"] = history["snapshot_date"].iloc[4]
    labels = label_observations(history)
    before_event = labels.loc[(labels["borrower_id"] == borrower) & (labels["observation_date"] == history["snapshot_date"].iloc[0])].iloc[0]
    assert before_event["new_npa_within_90d"] == 1
    late_observation = labels.loc[labels["observation_date"] == history["snapshot_date"].iloc[4]].iloc[0]
    assert pd.isna(late_observation["new_npa_within_90d"])


def test_invalid_non_synthetic_data_fails_validation():
    history = generate_synthetic_history(n_borrowers=2, seed=4)
    history.loc[history.index[0], "is_synthetic"] = False
    with pytest.raises(ValueError, match="marked synthetic"):
        validate_history(history)
