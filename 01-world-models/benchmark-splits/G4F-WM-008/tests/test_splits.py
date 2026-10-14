import pandas as pd
import pytest
from conftest import TEST_START, VALID_START

from splits import DROP, make_splits


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
    assert res.manifest["entities"] == {"train": 36, "valid": 12, "test": 12}


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
