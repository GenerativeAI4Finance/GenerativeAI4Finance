"""Input contract: a predictions file and an outcomes file, joined on a key.

See README.md for the column list. Validation is strict on purpose: a bad
row should stop the run, not quietly drop out of the metrics.
"""

import pandas as pd

SCENARIOS = ("baseline", "normal", "stress")
KEY = ["entity_id", "as_of", "horizon", "scenario"]
STATE_PREFIX = "p_state_"


class ContractError(ValueError):
    pass


def _require(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ContractError(f"{name} is missing columns: {missing}")


def state_columns(predictions):
    return [c for c in predictions.columns if c.startswith(STATE_PREFIX)]


def validate(predictions, outcomes):
    _require(predictions, KEY + ["p_event"], "predictions")
    _require(outcomes, KEY + ["event"], "outcomes")

    for name, df in (("predictions", predictions), ("outcomes", outcomes)):
        bad = sorted(set(df["scenario"]) - set(SCENARIOS))
        if bad:
            raise ContractError(f"{name} has unknown scenario labels: {bad}")
        dupes = df.duplicated(KEY)
        if dupes.any():
            raise ContractError(f"{name} has {int(dupes.sum())} duplicate rows on {KEY}")
        if df[KEY].isna().any().any():
            raise ContractError(f"{name} has missing values in key columns")

    p = pd.to_numeric(predictions["p_event"], errors="coerce")
    if p.isna().any():
        raise ContractError("p_event has missing or non-numeric values")
    if ((p < 0) | (p > 1)).any():
        raise ContractError("p_event values must be in [0, 1]")

    if not outcomes["event"].isin([0, 1]).all():
        raise ContractError("event must be 0 or 1")

    states = state_columns(predictions)
    if states:
        if "next_state" not in outcomes.columns:
            raise ContractError("p_state_* columns given but outcomes has no next_state")
        sp = predictions[states].apply(pd.to_numeric, errors="coerce")
        if sp.isna().any().any() or ((sp < 0) | (sp > 1)).any().any():
            raise ContractError("p_state_* values must be numeric and in [0, 1]")
        if ((sp.sum(axis=1) - 1).abs() > 1e-6).any():
            raise ContractError("p_state_* columns must sum to 1 on every row")
        known = {c[len(STATE_PREFIX) :] for c in states}
        unknown = sorted(set(outcomes["next_state"].dropna()) - known)
        if unknown:
            raise ContractError(f"next_state values without a p_state_ column: {unknown}")


def load(predictions_path, outcomes_path):
    predictions = pd.read_csv(predictions_path, dtype={"entity_id": str, "as_of": str})
    outcomes = pd.read_csv(outcomes_path, dtype={"entity_id": str, "as_of": str})
    return join(predictions, outcomes)


def join(predictions, outcomes):
    validate(predictions, outcomes)
    merged = predictions.merge(outcomes, on=KEY, how="left", indicator=True)
    unmatched = int((merged["_merge"] != "both").sum())
    if unmatched:
        raise ContractError(f"{unmatched} prediction rows have no matching outcome")
    extra = len(outcomes) - len(predictions)
    if extra > 0:
        raise ContractError(f"{extra} outcome rows have no matching prediction")
    merged = merged.drop(columns="_merge")
    merged["p_event"] = merged["p_event"].astype(float)
    merged["event"] = merged["event"].astype(int)
    return merged
