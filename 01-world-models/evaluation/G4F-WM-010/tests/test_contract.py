import pandas as pd
import pytest

from scenario_eval.contract import ContractError, join


def frames():
    key = {
        "entity_id": ["a", "b", "c"],
        "as_of": ["2025-01-31"] * 3,
        "horizon": [12] * 3,
        "scenario": ["baseline", "normal", "stress"],
    }
    preds = pd.DataFrame({**key, "p_event": [0.1, 0.2, 0.3]})
    outs = pd.DataFrame({**key, "event": [0, 1, 1]})
    return preds, outs


def test_valid_join():
    preds, outs = frames()
    df = join(preds, outs)
    assert len(df) == 3
    assert df["event"].tolist() == [0, 1, 1]


def test_unknown_scenario_label():
    preds, outs = frames()
    preds.loc[0, "scenario"] = "severe"
    with pytest.raises(ContractError, match="unknown scenario"):
        join(preds, outs)


def test_duplicate_key():
    preds, outs = frames()
    preds = pd.concat([preds, preds.iloc[[0]]])
    with pytest.raises(ContractError, match="duplicate"):
        join(preds, outs)


def test_prediction_without_outcome():
    preds, outs = frames()
    with pytest.raises(ContractError, match="no matching outcome"):
        join(preds, outs.iloc[:2])


def test_outcome_without_prediction():
    preds, outs = frames()
    with pytest.raises(ContractError, match="no matching prediction"):
        join(preds.iloc[:2], outs)


@pytest.mark.parametrize("value", [1.5, -0.01])
def test_probability_out_of_range(value):
    preds, outs = frames()
    preds.loc[1, "p_event"] = value
    with pytest.raises(ContractError, match=r"\[0, 1\]"):
        join(preds, outs)


def test_missing_column():
    preds, outs = frames()
    with pytest.raises(ContractError, match="missing columns"):
        join(preds.drop(columns="horizon"), outs)


def test_state_probabilities_must_sum_to_one():
    preds, outs = frames()
    preds["p_state_current"] = [0.9, 0.8, 0.6]
    preds["p_state_default"] = [0.1, 0.2, 0.3]
    outs["next_state"] = ["current", "default", "default"]
    with pytest.raises(ContractError, match="sum to 1"):
        join(preds, outs)


def test_state_columns_need_next_state():
    preds, outs = frames()
    preds["p_state_current"] = [0.9, 0.8, 0.7]
    preds["p_state_default"] = [0.1, 0.2, 0.3]
    with pytest.raises(ContractError, match="next_state"):
        join(preds, outs)


def with_states(from_state=None):
    preds, outs = frames()
    preds["p_state_current"] = [0.9, 0.8, 0.7]
    preds["p_state_default"] = [0.1, 0.2, 0.3]
    outs["next_state"] = ["current", "default", "default"]
    if from_state:
        preds["from_state"] = from_state
    return preds, outs


def test_valid_state_join():
    preds, outs = with_states(from_state=["current", "current", "late"])
    df = join(preds, outs)
    assert df["next_state"].tolist() == ["current", "default", "default"]
    assert df["from_state"].tolist() == ["current", "current", "late"]


@pytest.mark.parametrize("bad", [None, float("nan")])
def test_nan_next_state_rejected(bad):
    preds, outs = with_states()
    outs["next_state"] = outs["next_state"].astype(object)
    outs.loc[0, "next_state"] = bad
    with pytest.raises(ContractError, match="next_state is missing"):
        join(preds, outs)


def test_unknown_next_state_rejected():
    preds, outs = with_states()
    outs.loc[0, "next_state"] = "bankrupt"
    with pytest.raises(ContractError, match="without a p_state_ column"):
        join(preds, outs)


@pytest.mark.parametrize("bad", [0, -3, 1.5, 12.0001, "abc", "", True, None])
def test_bad_horizons_rejected(bad):
    preds, outs = frames()
    preds["horizon"] = preds["horizon"].astype(object)
    preds.loc[0, "horizon"] = bad
    with pytest.raises(ContractError, match="horizon|missing values"):
        join(preds, outs)


def test_horizon_spellings_match_across_files():
    preds, outs = frames()
    preds["horizon"] = ["12", "12.0", 12.0]
    df = join(preds, outs)
    assert df["horizon"].tolist() == [12, 12, 12]


@pytest.mark.parametrize(
    "bad", ["2025-02-30", "2025-13-01", "31/01/2025", "yesterday", "2025-1-31", ""]
)
def test_invalid_as_of_rejected(bad):
    preds, outs = frames()
    preds.loc[0, "as_of"] = bad
    with pytest.raises(ContractError, match="as_of"):
        join(preds, outs)


def test_as_of_timestamps_are_accepted_as_dates():
    preds, outs = frames()
    preds["as_of"] = pd.to_datetime(preds["as_of"])
    assert join(preds, outs)["as_of"].tolist() == ["2025-01-31"] * 3


@pytest.mark.parametrize("which", ["predictions", "outcomes"])
def test_duplicates_after_canonicalisation(which):
    preds, outs = frames()
    frame = preds if which == "predictions" else outs
    frame["horizon"] = frame["horizon"].astype(object)
    dup = frame.iloc[[0]].copy()
    dup["horizon"] = "12.0"
    frame = pd.concat([frame, dup], ignore_index=True)
    preds, outs = (frame, outs) if which == "predictions" else (preds, frame)
    with pytest.raises(ContractError, match="duplicate"):
        join(preds, outs)


def test_duplicate_entity_spelling_after_canonicalisation():
    preds, outs = frames()
    preds["entity_id"] = [1, "1", 2]
    preds["scenario"] = "normal"
    outs["scenario"] = "normal"
    with pytest.raises(ContractError, match="duplicate"):
        join(preds, outs)


def test_prediction_columns_in_outcomes_rejected():
    preds, outs = frames()
    outs["p_event"] = [0.1, 0.2, 0.3]
    with pytest.raises(ContractError, match="go in predictions"):
        join(preds, outs)
    preds, outs = with_states()
    outs["p_state_current"] = 0.5
    with pytest.raises(ContractError, match="go in predictions"):
        join(preds, outs)


def test_outcome_columns_in_predictions_rejected():
    preds, outs = frames()
    preds["next_state"] = ["a", "b", "c"]
    with pytest.raises(ContractError, match="go in outcomes"):
        join(preds, outs)


def test_p_event_must_match_p_state_default():
    preds, outs = with_states()
    preds.loc[0, "p_event"] = 0.5
    with pytest.raises(ContractError, match="p_event differs"):
        join(preds, outs)


def test_event_must_match_next_state_default():
    preds, outs = with_states()
    outs["event"] = [1, 1, 1]
    with pytest.raises(ContractError, match="event disagrees"):
        join(preds, outs)


def test_event_flag_must_be_zero_or_one():
    preds, outs = frames()
    outs.loc[0, "event"] = 2
    with pytest.raises(ContractError, match="0 or 1"):
        join(preds, outs)
