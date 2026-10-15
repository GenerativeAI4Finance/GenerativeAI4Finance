import pandas as pd
import pytest
from conftest import TEST_START, VALID_START

from splits import DROP, entity_bucket, make_splits


def split(df, spec, policy, **kw):
    kw.setdefault("valid_start", VALID_START)
    kw.setdefault("test_start", TEST_START)
    return make_splits(df, spec, policy, **kw)


@pytest.mark.parametrize("policy", ["time", "entity", "time_entity"])
def test_same_seed_same_split(panel, policy):
    df, spec = panel
    a = split(df, spec, policy, seed=3)
    b = split(df, spec, policy, seed=3)
    assert a.labels.equals(b.labels)
    assert a.manifest == b.manifest


def test_row_order_does_not_change_assignment(panel):
    df, spec = panel
    a = split(df, spec, "time_entity", seed=3)
    shuffled = df.sample(frac=1, random_state=1)
    b = split(shuffled, spec, "time_entity", seed=3)
    assert a.manifest["assignment_sha256"] == b.manifest["assignment_sha256"]


def test_different_seed_changes_entity_split(panel):
    df, spec = panel
    a = split(df, spec, "entity", seed=1)
    b = split(df, spec, "entity", seed=2)
    assert a.manifest["assignment_sha256"] != b.manifest["assignment_sha256"]


def test_time_split_purges_outcome_window(panel):
    df, spec = panel
    res = split(df, spec, "time")
    times = df[spec.time_col]
    train_max = times[res.labels == "train"].max()
    valid_max = times[res.labels == "valid"].max()
    assert train_max + spec.horizon <= pd.Timestamp(VALID_START)
    assert valid_max + spec.horizon <= pd.Timestamp(TEST_START)
    assert times[res.labels == "test"].min() == pd.Timestamp(TEST_START)
    # The purge gap rows are dropped, not silently moved elsewhere.
    assert res.manifest["rows"][DROP] > 0


def test_embargo_widens_gap(panel):
    df, spec = panel
    plain = split(df, spec, "time")
    wider = split(df, spec, "time", embargo=pd.Timedelta(days=60))
    assert wider.manifest["rows"]["train"] < plain.manifest["rows"]["train"]


def test_entity_split_keeps_entities_whole(panel):
    df, spec = panel
    res = split(df, spec, "entity", fractions=(0.6, 0.2, 0.2))
    per_entity = res.labels.groupby(df[spec.entity_col]).nunique()
    assert (per_entity == 1).all()
    # Entities are placed by hash, so the shares are close to the fractions
    # but not exact.
    assert res.manifest["entities"] == {"train": 37, "valid": 13, "test": 10}


def test_manifest_records_what_is_needed_to_rerun(panel):
    df, spec = panel
    m = split(df, spec, "time_entity", seed=5).manifest
    for key in ("policy", "seed", "fractions", "valid_start", "test_start", "embargo"):
        assert m[key] is not None
    assert len(m["assignment_sha256"]) == 64
    assert sum(m["rows"].values()) == len(df)


def test_bad_inputs_are_rejected(panel):
    df, spec = panel
    with pytest.raises(ValueError, match="unknown policy"):
        make_splits(df, spec, "random")
    with pytest.raises(ValueError, match="valid_start"):
        make_splits(df, spec, "time")
    with pytest.raises(ValueError, match="before test_start"):
        split(df, spec, "time", valid_start=TEST_START, test_start=VALID_START)
    with pytest.raises(ValueError, match="fractions"):
        split(df, spec, "entity", fractions=(0.5, 0.5, 0.5))
    with pytest.raises(ValueError, match="duplicate"):
        split(pd.concat([df, df.head(1)]), spec, "entity")


def test_assignment_hash_is_fixed_for_a_fixed_input(panel):
    df, spec = panel
    m = split(df, spec, "time_entity", seed=0).manifest
    # Pin the assignment and its nanosecond-preserving serialization.
    assert m["rows"] == {"train": 688, "valid": 63, "test": 72, "drop": 1337}
    assert m["assignment_sha256"] == (
        "dc42b5b987b18054a5fa0b452f6b2d5f2632287a18999da54985b459a8b0eef7"
    )
    assert 0 <= entity_bucket("E000", 0) < 1


def test_entity_assignment_is_stable_when_other_entities_change(panel):
    df, spec = panel
    before = (
        split(df, spec, "entity", seed=2).labels.groupby(df[spec.entity_col]).first()
    )
    removed = {"E003", "E010", "E044"}
    extra = df[df[spec.entity_col] == "E001"].copy()
    extra[spec.entity_col] = "NEW1"
    changed = pd.concat(
        [df[~df[spec.entity_col].isin(removed)], extra], ignore_index=True
    )
    res = split(changed, spec, "entity", seed=2)
    after = res.labels.groupby(changed[spec.entity_col]).first()
    kept = [e for e in before.index if e not in removed]
    assert (after[kept] == before[kept]).all()


def test_entity_split_with_too_few_entities_raises(panel):
    df, spec = panel
    two = df[df[spec.entity_col].isin(["E000", "E001"])]
    with pytest.raises(ValueError, match="would be empty"):
        split(two, spec, "entity")


def test_time_split_with_cutoffs_past_the_data_raises(panel):
    df, spec = panel
    with pytest.raises(ValueError, match="would be empty"):
        split(df, spec, "time", valid_start="2030-01-01", test_start="2031-01-01")


@pytest.mark.parametrize(
    "fractions",
    [
        (0.5, 0.5, 0.5),
        (1.0, 0.0, 0.0),
        (0.8, 0.2),
        (-0.1, 0.6, 0.5),
        (float("nan"), 0.5, 0.5),
        "abc",
        None,
    ],
)
def test_bad_fractions_are_rejected(panel, fractions):
    df, spec = panel
    with pytest.raises(ValueError, match="fractions"):
        split(df, spec, "entity", fractions=fractions)


def test_boundary_rows_are_included_where_documented(panel):
    df, spec = panel
    res = split(df, spec, "time")
    times = df[spec.time_col]
    label_at = lambda ts: set(res.labels[times == pd.Timestamp(ts)])
    # t == valid_start / test_start opens the later split.
    assert label_at(VALID_START) == {"valid"}
    assert label_at(TEST_START) == {"test"}
    # t + horizon == valid_start is the last train row; the next month is dropped.
    assert label_at("2022-04-01") == {"train"}
    assert label_at("2022-05-01") == {DROP}
    assert label_at("2023-01-01") == {"valid"}
    assert label_at("2023-02-01") == {DROP}


def test_embargo_counts_toward_the_boundary(panel):
    df, spec = panel
    res = split(df, spec, "time", embargo=pd.Timedelta(days=1))
    times = df[spec.time_col]
    # 2022-04-01 + 3 months + 1 day is past valid_start.
    assert set(res.labels[times == pd.Timestamp("2022-04-01")]) == {DROP}


def test_timezone_mismatch_is_rejected_and_aware_data_works(panel):
    df, spec = panel
    aware = df.copy()
    aware[spec.time_col] = aware[spec.time_col].dt.tz_localize("UTC")
    aware["dpd_observed_at"] = aware["dpd_observed_at"].dt.tz_localize("UTC")
    with pytest.raises(ValueError, match="timezone"):
        split(aware, spec, "time")
    ok = split(
        aware,
        spec,
        "time",
        valid_start="2022-07-01T00:00:00+00:00",
        test_start="2023-04-01T00:00:00+00:00",
    )
    naive = split(df, spec, "time")
    assert ok.manifest["rows"] == naive.manifest["rows"]
    # Same wall clock in another zone is a different instant, so a different hash.
    assert ok.manifest["assignment_sha256"] != naive.manifest["assignment_sha256"]
    with pytest.raises(ValueError, match="timezone"):
        split(
            df,
            spec,
            "time",
            valid_start="2022-07-01T00:00:00+00:00",
            test_start="2023-04-01T00:00:00+00:00",
        )


def test_missing_entity_ids_and_timestamps_are_rejected(panel):
    df, spec = panel
    no_id = df.copy()
    no_id.loc[no_id.index[0], spec.entity_col] = None
    with pytest.raises(ValueError, match="missing values"):
        split(no_id, spec, "entity")
    no_time = df.copy()
    no_time.loc[no_time.index[0], spec.time_col] = pd.NaT
    with pytest.raises(ValueError, match="NaT"):
        split(no_time, spec, "time")


@pytest.mark.parametrize(
    "horizon",
    [pd.Timedelta(days=-1), pd.DateOffset(months=-3), pd.NaT, "3 months", -1],
)
@pytest.mark.parametrize("policy", ["time", "entity", "time_entity"])
def test_invalid_horizon_is_rejected(panel, horizon, policy):
    df, spec = panel
    spec.horizon = horizon
    with pytest.raises(ValueError, match="horizon"):
        split(df, spec, policy)


@pytest.mark.parametrize("embargo", [pd.Timedelta(days=-1), pd.NaT, "-1 day", -1])
@pytest.mark.parametrize("policy", ["time", "entity", "time_entity"])
def test_invalid_embargo_is_rejected(panel, embargo, policy):
    df, spec = panel
    with pytest.raises(ValueError, match="embargo"):
        split(df, spec, policy, embargo=embargo)


@pytest.mark.parametrize("timezone", [None, "UTC", "Asia/Kolkata"])
def test_assignment_hash_preserves_nanoseconds_and_row_order(panel, timezone):
    from splits import assignment_hash

    df, spec = panel
    df = df.copy()
    df[spec.time_col] = df[spec.time_col].dt.as_unit("ns")
    if timezone:
        df[spec.time_col] = df[spec.time_col].dt.tz_localize(timezone)
    labels = pd.Series("train", index=df.index)
    original = assignment_hash(df, labels, spec)
    df.loc[df.index[0], spec.time_col] += pd.Timedelta(nanoseconds=1)
    changed = assignment_hash(df, labels, spec)
    assert changed != original
    shuffled = df.sample(frac=1, random_state=15)
    assert assignment_hash(shuffled, labels.loc[shuffled.index], spec) == changed
