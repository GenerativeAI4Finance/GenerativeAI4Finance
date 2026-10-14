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
