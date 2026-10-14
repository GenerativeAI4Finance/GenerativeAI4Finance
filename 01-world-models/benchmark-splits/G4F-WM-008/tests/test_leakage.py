"""Each check gets a clean case and at least one known-failure fixture."""

import json

import numpy as np
import pandas as pd
import pytest
from conftest import TEST_START, VALID_START

from leakage import (
    check_entity_overlap,
    check_feature_timestamps,
    check_near_duplicates,
    check_post_outcome_fields,
    check_target_leakage,
    check_time_order,
    run_checks,
    to_json,
)
from splits import make_splits


def split(df, spec, policy="time_entity", seed=0):
    return make_splits(
        df, spec, policy, valid_start=VALID_START, test_start=TEST_START, seed=seed
    )


@pytest.mark.parametrize("policy", ["time", "entity", "time_entity"])
def test_clean_panel_passes_everything(panel, policy):
    df, spec = panel
    res = split(df, spec, policy)
    report = run_checks(df, res.labels, spec, res.manifest)
    assert report["ok"], report["failed"]
    json.loads(to_json(report))


def test_entity_overlap_fixture(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    labels = res.labels.copy()
    entity = df.loc[labels == "train", spec.entity_col].iloc[0]
    # Move one row of a train entity into test.
    row = df.index[(df[spec.entity_col] == entity)][0]
    labels[row] = "test"

    out = check_entity_overlap(df, labels, spec)
    assert out["status"] == "fail"
    assert out["entities"] == [entity]
    assert run_checks(df, labels, spec, res.manifest)["failed"] == ["entity_overlap"]


def test_near_duplicate_fixture(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    source = df.loc[res.labels == "train", spec.entity_col].iloc[0]

    # Same borrower re-keyed under a new id, with tiny noise, landing in test.
    clone = df[df[spec.entity_col] == source].copy()
    clone[spec.entity_col] = "E999"
    rng = np.random.default_rng(0)
    clone[spec.feature_cols] += rng.normal(0, 1e-7, clone[spec.feature_cols].shape)
    df2 = pd.concat([df, clone], ignore_index=True)
    labels = pd.concat(
        [res.labels, pd.Series("test", index=clone.index)], ignore_index=True
    )

    assert check_entity_overlap(df2, labels, spec)["status"] == "pass"
    out = check_near_duplicates(df2, labels, spec)
    assert out["status"] == "fail"
    assert out["groups"] == [[(source, "train"), ("E999", "test")]]


def test_near_duplicate_ignores_distinct_trajectories(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    assert check_near_duplicates(df, res.labels, spec)["status"] == "pass"


def test_time_order_fixture(panel):
    df, spec = panel
    # Split without the purge gap: train runs right up to the validation start,
    # so the last train labels are observed inside the validation period.
    times = df[spec.time_col]
    labels = pd.Series("test", index=df.index)
    labels[times < pd.Timestamp(TEST_START)] = "valid"
    labels[times < pd.Timestamp(VALID_START)] = "train"

    out = check_time_order(df, labels, spec)
    assert out["status"] == "fail"
    pairs = {(v["earlier"], v["later"]) for v in out["violations"]}
    assert pairs == {("train", "valid"), ("valid", "test")}


def test_feature_timestamp_fixture(panel):
    df, spec = panel
    df = df.copy()
    # Bureau value revised after the prediction date and back-filled.
    rows = df.index[:5]
    df.loc[rows, "dpd_observed_at"] = df.loc[rows, "timestamp"] + pd.Timedelta(days=20)
    res = split(df, spec, "entity")
    out = check_feature_timestamps(df, res.labels, spec)
    assert out["status"] == "fail"
    assert out["rows_observed_after_prediction_time"] == {"days_past_due": 5}


def test_feature_timestamp_skipped_without_declaration(panel):
    df, spec = panel
    spec.observed_at = {}
    res = split(df, spec, "entity")
    assert check_feature_timestamps(df, res.labels, spec)["status"] == "skipped"


def test_post_outcome_fixture(panel):
    df, spec = panel
    spec.feature_cols = [*spec.feature_cols, "recovery_amount", spec.target_col]
    res = split(df, spec, "entity")
    out = check_post_outcome_fields(df, res.labels, spec)
    assert out["status"] == "fail"
    assert out["features"] == ["recovery_amount", spec.target_col]


def test_target_copy_fixture(panel):
    df, spec = panel
    df = df.copy()
    df["flag_copy"] = df[spec.target_col]
    spec.feature_cols = [*spec.feature_cols, "flag_copy"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    assert out["status"] == "fail"
    assert {s["feature"] for s in out["suspects"]} == {"flag_copy"}


def test_shifted_target_fixture(panel):
    df, spec = panel
    df = df.sort_values([spec.entity_col, spec.time_col]).copy()
    # Next period's label joined onto this row, e.g. from a bad merge key.
    df["next_label"] = df.groupby(spec.entity_col)[spec.target_col].shift(-2)
    spec.feature_cols = [*spec.feature_cols, "next_label"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    hit = [s for s in out["suspects"] if s["feature"] == "next_label"]
    assert out["status"] == "fail"
    assert hit[0]["reason"] == "equals_target"
    assert hit[0]["shift"] == 2


def test_near_perfect_predictor_fixture(panel):
    df, spec = panel
    df = df.copy()
    rng = np.random.default_rng(1)
    # Something like a collections score that was computed after the default.
    df["collections_score"] = df[spec.target_col] * 10 + rng.uniform(0, 1, len(df))
    spec.feature_cols = [*spec.feature_cols, "collections_score"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    hit = [s for s in out["suspects"] if s["feature"] == "collections_score"]
    assert hit and hit[0]["reason"] == "near_perfect_predictor"
    assert hit[0]["auc"] == 1.0


def test_continuous_target_uses_rank_correlation(panel):
    df, spec = panel
    df = df.copy()
    df["loss"] = df["recovery_amount"]
    df["loss_cents"] = df["loss"] * 100 + 3
    spec.target_col = "loss"
    spec.feature_cols = [*spec.feature_cols, "loss_cents"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    assert [s["feature"] for s in out["suspects"]] == ["loss_cents"]
    assert out["suspects"][0]["abs_rank_corr"] >= 0.99
