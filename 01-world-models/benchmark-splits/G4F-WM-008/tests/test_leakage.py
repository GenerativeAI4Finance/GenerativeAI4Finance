"""Each check gets a clean case and at least one known-failure fixture."""

import json

import numpy as np
import pandas as pd
import pytest
from conftest import TEST_START, VALID_START, cached_panel

from leakage import (
    align_trajectories,
    check_entity_overlap,
    check_feature_timestamps,
    check_near_duplicates,
    check_post_outcome_fields,
    check_split_sizes,
    check_target_leakage,
    check_time_order,
    run_checks,
    to_json,
)
from panel import PanelSpec
from splits import _entity_groups, make_splits


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
    assert report["all_applicable_checks_passed"], report["skipped"]
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
    assert [p["entities"] for p in out["pairs"]] == [
        [(source, "train"), ("E999", "test")]
    ]


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
    assert out["features"]["days_past_due"]["late"] == 5
    assert out["features"]["days_past_due"]["unknown"] == 0


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
    # The label from two rows ahead joined onto this row, e.g. from a bad merge key.
    df["next_label"] = df.groupby(spec.entity_col)[spec.target_col].shift(-2)
    spec.feature_cols = [*spec.feature_cols, "next_label"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    hit = [s for s in out["suspects"] if s["feature"] == "next_label"]
    assert out["status"] == "fail"
    assert hit[0]["reason"] == "copies_target"
    assert hit[0]["shift"] == 2
    assert hit[0]["kappa"] >= 0.99


@pytest.mark.parametrize("policy", ["time", "entity", "time_entity"])
@pytest.mark.parametrize("shift", [1, 2, 3])
@pytest.mark.parametrize("continuous", [False, True])
def test_noisy_shifted_target_uses_full_history(panel, policy, shift, continuous):
    df, spec = panel
    df = df.sort_values([spec.entity_col, spec.time_col]).copy()
    rng = np.random.default_rng(40)
    if continuous:
        df[spec.target_col] = rng.normal(size=len(df))
    future = df.groupby(spec.entity_col)[spec.target_col].shift(-shift)
    df["noisy_future"] = future * 10 + rng.uniform(0, 0.01, len(df))
    spec.feature_cols = ["noisy_future"]
    res = split(df, spec, policy)
    out = check_target_leakage(df, res.labels, spec)
    assert out["status"] == "fail", out
    hit = next(s for s in out["suspects"] if s["feature"] == "noisy_future")
    assert hit["reason"] == "near_perfect_predictor"
    assert hit["shift"] == shift


@pytest.mark.parametrize("policy", ["time", "entity", "time_entity"])
@pytest.mark.parametrize("continuous", [False, True])
@pytest.mark.parametrize("noisy_score", [False, True])
def test_observed_lag_of_persistent_outcome_is_allowed(
    panel, policy, continuous, noisy_score
):
    df, spec = panel
    df = df.sort_values([spec.entity_col, spec.time_col]).copy()
    entity_number = df[spec.entity_col].str[1:].astype(int)
    df[spec.target_col] = entity_number if continuous else entity_number % 2
    known = df.groupby(spec.entity_col)[spec.target_col].shift(3)
    df["known_lag"] = known
    if noisy_score:
        df["known_lag"] = known * 10 + np.random.default_rng(41).uniform(
            0, 0.001, len(df)
        )
    spec.feature_cols = ["known_lag"]
    res = split(df, spec, policy)
    out = check_target_leakage(df, res.labels, spec)
    assert out["status"] == "pass", out
    assert out["suspects"] == []


def test_target_leakage_does_not_evaluate_dropped_feature_rows(panel):
    df, spec = panel
    res = split(df, spec)
    df["dropped_copy"] = df[spec.target_col].where(res.labels == "drop")
    spec.feature_cols = ["dropped_copy"]
    out = check_target_leakage(df, res.labels, spec)
    assert out["status"] == "skipped"
    assert out["skipped_features"] == {"dropped_copy": "constant"}


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


def with_clone(df, spec, source, variant):
    """Add a copy of `source` under a new id, altered the way a duplicated
    record tends to be. The new id is picked so the entity hash puts it in
    a different group from the source."""
    fractions = (0.7, 0.15, 0.15)
    group = _entity_groups(df[spec.entity_col], fractions, 0)[source]
    n = 0
    while True:
        new_id = f"CLONE{n}"
        if _entity_groups(pd.Series([new_id]), fractions, 0)[new_id] != group:
            break
        n += 1
    clone = df[df[spec.entity_col] == source].copy()
    clone[spec.entity_col] = new_id
    feats = spec.feature_cols
    if variant == "noise":
        noise = np.random.default_rng(4).normal(0, 1, clone[feats].shape)
        clone[feats] += noise * df[feats].std().to_numpy() * 0.02
    elif variant == "scale":
        clone[feats] *= 1.01
    elif variant == "dropped_row":
        clone = clone.drop(clone.index[10])
    elif variant == "later_start":
        clone = clone.iloc[1:]
    elif variant == "shifted_dates":
        clone[spec.time_col] += pd.DateOffset(months=6)
    return pd.concat([df, clone], ignore_index=True), new_id


@pytest.mark.parametrize(
    "variant",
    ["exact", "noise", "scale", "dropped_row", "later_start", "shifted_dates"],
)
def test_clone_variants_found_under_time_entity(panel, variant):
    df, spec = panel
    source = "E017"
    df2, clone_id = with_clone(df, spec, source, variant)
    res = split(df2, spec, "time_entity")
    out = check_near_duplicates(df2, res.labels, spec)
    assert out["status"] == "fail"
    found = [{e for e, _ in p["entities"]} for p in out["pairs"]]
    assert {source, clone_id} in found


def test_missing_row_tolerance_boundary(panel):
    """The allowance is 5% of the longer history (at least 1 row): with
    fewer than 40 rows that is one row, so two dropped rows are missed."""
    df, spec = panel
    source = "E017"
    df2, clone_id = with_clone(df, spec, source, "exact")
    assert 20 <= (df2[spec.entity_col] == source).sum() < 40
    clone_rows = df2.index[df2[spec.entity_col] == clone_id]
    res = split(df2, spec, "time_entity")
    for dropped, caught in ((1, True), (2, False)):
        trimmed = df2.drop(clone_rows[[10, 20][:dropped]]).reset_index(drop=True)
        labels = res.labels.drop(clone_rows[[10, 20][:dropped]]).reset_index(drop=True)
        out = check_near_duplicates(trimmed, labels, spec)
        found = [{e for e, _ in p["entities"]} for p in out.get("pairs", [])]
        assert ({source, clone_id} in found) is caught


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_unrelated_entities_are_not_flagged(seed):
    df, spec = cached_panel(seed=seed)
    res = split(df, spec, "time_entity", seed=seed)
    out = check_near_duplicates(df, res.labels, spec)
    assert out["status"] == "pass", out["pairs"]
    assert out["compared_entities"] > 30


def test_near_duplicates_ignore_dormant_entities(panel):
    df, spec = panel
    df = df.copy()
    # Two flat histories look identical, but that is not evidence of a copy.
    for entity in ("E001", "E002"):
        df.loc[df[spec.entity_col] == entity, spec.feature_cols] = 0.0
    res = split(df, spec, "entity")
    out = check_near_duplicates(df, res.labels, spec)
    assert out["status"] == "pass"
    assert out["low_information"]["n_entities"] >= 2


def test_near_duplicates_skipped_when_nothing_to_compare(panel):
    df, spec = panel
    df = df.copy()
    df["note"] = "x"
    spec.feature_cols = ["note"]
    res = split(df, spec, "entity")
    out = check_near_duplicates(df, res.labels, spec)
    assert out["status"] == "skipped"
    assert out["ignored_features"] == {"note": "not numeric"}


def test_near_duplicates_without_informative_cross_split_pairs_is_unverified(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    df.loc[res.labels != "train", spec.feature_cols] = 0.0
    out = check_near_duplicates(df, res.labels, spec)
    assert out["status"] == "skipped"
    assert out["cross_split_candidates"] == out["aligned_pairs"] == 0
    assert out["compared_entities"] > 2
    report = run_checks(df, res.labels, spec, res.manifest)
    assert report["ok"]  # This means no failure, not that all checks ran.
    assert not report["all_applicable_checks_passed"]
    assert "near_duplicate_trajectories" in report["skipped"]


def test_near_duplicates_without_eligible_alignments_is_skipped(panel):
    df, spec = panel
    # Both histories have enough information, but their lengths cannot align.
    df = pd.concat(
        [df[df.entity_id == "E000"].head(8), df[df.entity_id == "E001"]],
        ignore_index=True,
    )
    labels = pd.Series(np.where(df.entity_id == "E000", "train", "test"))
    out = check_near_duplicates(df, labels, spec)
    assert out["status"] == "skipped"
    assert out["cross_split_candidates"] == 1
    assert out["aligned_pairs"] == 0


def test_alignment_limits_total_gaps_even_when_displacement_cancels():
    a = np.array([1.9, -5.2, -4.1, -24.4, 18.0])[:, None]
    b = np.array([11.4, -3.3, 7.7, 2.8, -5.5])[:, None]
    rms, unmatched = align_trajectories(a, b, max_skip=1)
    # Equal-length paths need two gaps to skip a row on both sides.
    assert unmatched == 0
    assert rms == pytest.approx(np.sqrt(np.mean((a - b) ** 2)))


def test_example_gate_requires_all_applicable_checks_to_pass(
    panel, monkeypatch, capsys
):
    import example

    df, spec = panel
    res = split(df, spec, "entity")
    df.loc[res.labels != "train", spec.feature_cols] = 0.0
    monkeypatch.setattr(example, "make_panel", lambda **kwargs: (df, spec))
    monkeypatch.setattr("sys.argv", ["example.py", "--policy", "entity"])
    assert example.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"]
    assert not report["all_applicable_checks_passed"]


def rare_target_panel(rate=0.03):
    df, spec = cached_panel(n_entities=80, seed=5)
    df = df.copy()
    rng = np.random.default_rng(0)
    df["rare_target"] = (rng.random(len(df)) < rate).astype(int)
    df["independent_flag"] = (rng.random(len(df)) < rate).astype(int)
    spec.target_col = "rare_target"
    return df, spec


def test_rare_target_copy_is_found_but_independent_flag_is_not():
    df, spec = rare_target_panel()
    df["copy"] = df["rare_target"]
    spec.feature_cols = [*spec.feature_cols, "copy", "independent_flag"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    assert {s["feature"] for s in out["suspects"]} == {"copy"}


def test_lagged_target_known_at_prediction_time_is_not_a_leak(panel):
    df, spec = panel
    df = df.sort_values([spec.entity_col, spec.time_col]).copy()
    by_entity = df.groupby(spec.entity_col)[spec.target_col]
    # Horizon is 3 months and rows are monthly: the label of the row 3 back
    # is fully observed at t, the label of the row 1 back is not.
    df["closed_label"] = by_entity.shift(3)
    df["open_label"] = by_entity.shift(1)
    spec.feature_cols = [*spec.feature_cols, "closed_label", "open_label"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    hits = {s["feature"]: s for s in out["suspects"]}
    assert "closed_label" not in hits
    assert hits["open_label"]["reason"] == "copies_target"
    assert hits["open_label"]["shift"] < 0


def test_target_leakage_skipped_on_tiny_or_one_sided_data(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    tiny = check_target_leakage(df.head(20), res.labels.head(20), spec)
    assert tiny["status"] == "skipped"
    assert "20 labelled rows" in tiny["reason"]

    one_sided = df.copy()
    one_sided[spec.target_col] = 0
    one_sided.loc[one_sided.index[:3], spec.target_col] = 1
    out = check_target_leakage(one_sided, res.labels, spec)
    assert out["status"] == "skipped"
    assert "3 positive" in out["reason"]


def test_target_leakage_skipped_when_no_feature_can_be_evaluated(panel):
    df, spec = panel
    df = df.copy()
    df["note"] = "x"
    df["empty"] = np.nan
    spec.feature_cols = ["note", "empty"]
    res = split(df, spec, "entity")
    out = check_target_leakage(df, res.labels, spec)
    assert out["status"] == "skipped"
    assert set(out["skipped_features"]) == {"note", "empty"}


def test_value_heuristic_flags_field_only_set_after_outcome(panel):
    df, spec = panel
    df = df.copy()
    # Filled in only once the loan defaulted, and not declared as post-outcome.
    df["collections_stage"] = np.where(df[spec.target_col] == 1, 2.0, np.nan)
    spec.feature_cols = [*spec.feature_cols, "collections_stage"]
    res = split(df, spec, "entity")
    out = check_post_outcome_fields(df, res.labels, spec)
    assert out["status"] == "fail"
    assert [s["feature"] for s in out["suspects"]] == ["collections_stage"]


def test_post_outcome_value_check_reports_when_it_did_not_run(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    out = check_post_outcome_fields(df.head(20), res.labels.head(20), spec)
    assert out["status"] == "pass"
    assert out["value_check"].startswith("skipped")


def test_rows_without_a_feature_value_need_no_timestamp(panel):
    df, spec = panel
    df = df.copy()
    df.loc[df.index[:4], "dpd_observed_at"] = pd.NaT
    res = split(df, spec, "entity")
    out = check_feature_timestamps(df, res.labels, spec)
    kept = int((res.labels.iloc[:4] != "drop").sum())
    assert kept > 0
    assert out["status"] == "fail"
    assert out["features"]["days_past_due"]["unknown"] == kept
    df.loc[df.index[:4], "days_past_due"] = np.nan
    out = check_feature_timestamps(df, res.labels, spec)
    assert out["status"] == "pass"
    assert out["features"]["days_past_due"]["unknown"] == 0


def test_missing_observed_at_fails_instead_of_passing(panel):
    df, spec = panel
    df = df.copy()
    df["dpd_observed_at"] = pd.NaT
    res = split(df, spec, "entity")
    out = check_feature_timestamps(df, res.labels, spec)
    assert out["status"] == "fail"
    assert out["features"]["days_past_due"]["rows_checked"] == 0
    assert out["features"]["days_past_due"]["unknown"] == res.manifest["rows_kept"]
    report = run_checks(df, res.labels, spec, res.manifest)
    assert "feature_timestamps" in report["failed"]


def test_feature_timestamps_skipped_when_every_feature_is_empty(panel):
    df, spec = panel
    df = df.copy()
    df["days_past_due"] = np.nan
    res = split(df, spec, "entity")
    out = check_feature_timestamps(df, res.labels, spec)
    assert out["status"] == "skipped"
    assert out["features"]["days_past_due"]["rows_checked"] == 0


def test_text_feature_does_not_crash_the_checks(panel):
    df, spec = panel
    df = df.copy()
    df["segment"] = np.where(df.index % 2, "retail", "sme")
    spec.feature_cols = [*spec.feature_cols, "segment"]
    res = split(df, spec, "time_entity")
    report = run_checks(df, res.labels, spec, res.manifest)
    assert report["ok"], report["failed"]
    checks = report["checks"]
    assert checks["near_duplicate_trajectories"]["ignored_features"] == {
        "segment": "not numeric"
    }
    assert checks["target_leakage"]["skipped_features"]["segment"] == "not numeric"


def test_split_sizes_fails_on_an_empty_split(panel):
    df, spec = panel
    labels = pd.Series("train", index=df.index)
    out = check_split_sizes(df, labels, spec)
    assert out["status"] == "fail"
    assert out["empty"] == ["valid", "test"]


def test_run_checks_rejects_bad_labels(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    with pytest.raises(ValueError, match="unknown split labels"):
        run_checks(df, res.labels.replace("test", "holdout"), spec, res.manifest)
    with pytest.raises(ValueError, match="same index"):
        run_checks(df, res.labels.iloc[:-1], spec, res.manifest)


def test_checks_that_do_not_apply_are_skipped_with_a_reason(panel):
    df, spec = panel
    res = split(df, spec, "time")
    report = run_checks(df, res.labels, spec, res.manifest)
    assert set(report["skipped"]) == {"entity_overlap", "near_duplicate_trajectories"}
    assert report["checks"]["entity_overlap"]["reason"]


def test_missing_ids_timestamps_and_columns_are_rejected(panel):
    df, spec = panel
    res = split(df, spec, "entity")
    no_id = df.copy()
    no_id.loc[no_id.index[0], spec.entity_col] = None
    with pytest.raises(ValueError, match="missing values"):
        run_checks(no_id, res.labels, spec, res.manifest)
    no_time = df.copy()
    no_time.loc[no_time.index[0], spec.time_col] = pd.NaT
    with pytest.raises(ValueError, match="NaT"):
        run_checks(no_time, res.labels, spec, res.manifest)
    with pytest.raises(ValueError, match="missing columns"):
        run_checks(df.drop(columns="income_ratio"), res.labels, spec, res.manifest)


def test_observed_at_timezone_must_match_timestamps(panel):
    df, spec = panel
    df = df.copy()
    df["dpd_observed_at"] = df["dpd_observed_at"].dt.tz_localize("UTC")
    with pytest.raises(ValueError, match="timezone"):
        spec.validate(df)


HELPER_NAMES = ["_entity", "_time", "_split", "_kept", "_y", "_window_end"]


@pytest.mark.parametrize("name", HELPER_NAMES)
def test_helper_names_are_valid_clean_feature_names(panel, name):
    df, spec = panel
    old = spec.feature_cols[0]
    df = df.rename(columns={old: name})
    spec.feature_cols[0] = name
    res = split(df, spec)
    report = run_checks(df, res.labels, spec, res.manifest)
    assert report["all_applicable_checks_passed"], report
    assert name in report["checks"]["target_leakage"]["features_evaluated"]


@pytest.mark.parametrize("name", HELPER_NAMES)
def test_helper_names_do_not_hide_future_target_scores(panel, name):
    df, spec = panel
    future = df.groupby(spec.entity_col)[spec.target_col].shift(-2)
    # A scaled score avoids the simpler only-set-after-outcome heuristic.
    df[name] = future * 10 + 0.001
    spec.feature_cols.append(name)
    res = split(df, spec)
    report = run_checks(df, res.labels, spec, res.manifest)
    assert not report["all_applicable_checks_passed"]
    assert "target_leakage" in report["failed"]
    hit = next(
        s
        for s in report["checks"]["target_leakage"]["suspects"]
        if s["feature"] == name
    )
    assert hit["shift"] == 2
    assert hit["reason"] == "near_perfect_predictor"


@pytest.mark.parametrize("name", HELPER_NAMES)
@pytest.mark.parametrize("role", ["entity_col", "time_col", "target_col"])
def test_helper_names_are_valid_schema_column_names(panel, name, role):
    df, spec = panel
    old = getattr(spec, role)
    df = df.rename(columns={old: name})
    setattr(spec, role, name)
    res = split(df, spec)
    report = run_checks(df, res.labels, spec, res.manifest)
    assert report["all_applicable_checks_passed"], report


def test_near_duplicates_preserve_distinct_native_entity_ids():
    df = pd.DataFrame(
        {
            "entity_id": [1] * 10 + ["1"] * 10,
            "timestamp": list(pd.date_range("2021-01-01", periods=10)) * 2,
            "feature": list(range(10)) * 2,
            "target": [0, 1] * 10,
        }
    )
    spec = PanelSpec(["feature"], "target", pd.Timedelta(days=1))
    labels = pd.Series(["train"] * 10 + ["test"] * 10)
    out = check_near_duplicates(df, labels, spec)
    assert out["status"] == "fail"
    assert out["n_pairs"] == 1
    assert out["compared_entities"] == 2
    shuffled = df.sample(frac=1, random_state=7)
    assert check_near_duplicates(shuffled, labels.loc[shuffled.index], spec) == out


def test_time_order_uses_latest_actual_outcome_window():
    df = pd.DataFrame(
        {
            "entity_id": ["a"] * 3,
            "timestamp": pd.to_datetime(["2022-12-01", "2023-01-01", "2030-06-01"]),
            "feature": [1, 2, 3],
            "target": [0, 1, 0],
        }
    )
    # Absolute year replacement plus a day is a valid positive horizon, but
    # the December row ends after the January row despite occurring first.
    spec = PanelSpec(["feature"], "target", pd.DateOffset(year=2030, days=1))
    spec.validate(df)
    labels = pd.Series(["train", "train", "test"])
    out = check_time_order(df, labels, spec)
    assert out["status"] == "fail"
    assert (
        out["violations"][0]["earlier_max_time_plus_horizon"] == "2030-12-02T00:00:00"
    )


def test_time_order_keeps_relative_calendar_horizon_behavior():
    df = pd.DataFrame(
        {
            "entity_id": ["a"] * 3,
            "timestamp": pd.to_datetime(["2022-12-01", "2023-01-01", "2023-06-01"]),
            "feature": [1, 2, 3],
            "target": [0, 1, 0],
        }
    )
    spec = PanelSpec(["feature"], "target", pd.DateOffset(months=1))
    labels = pd.Series(["train", "train", "test"])
    assert check_time_order(df, labels, spec)["status"] == "pass"


@pytest.mark.parametrize("dtype", ["Float64", "string"])
@pytest.mark.parametrize("missing_only_on_positive", [False, True])
def test_post_outcome_nullable_features_count_missing_as_a_value(
    dtype, missing_only_on_positive
):
    feature = pd.Series([0] * 20 + [1] * 20, dtype=dtype)
    if missing_only_on_positive:
        feature.iloc[20:] = pd.NA
    else:
        feature.iloc[0] = pd.NA
    df = pd.DataFrame(
        {
            "entity_id": ["a"] * 40,
            "timestamp": pd.date_range("2021-01-01", periods=40),
            "feature": feature,
            "target": [0] * 20 + [1] * 20,
        }
    )
    spec = PanelSpec(["feature"], "target", pd.Timedelta(days=1))
    out = check_post_outcome_fields(df, pd.Series("train", index=df.index), spec)
    assert out["value_check"] == "ran"
    assert out["status"] == ("fail" if missing_only_on_positive else "pass")
    if missing_only_on_positive:
        assert out["suspects"][0]["share_of_positive_rows"] == 1.0
        assert out["suspects"][0]["share_of_negative_rows"] == 0.0
