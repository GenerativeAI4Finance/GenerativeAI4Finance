"""Input contract: a predictions file and an outcomes file, joined on a key.

See README.md for the column list. Validation is strict on purpose: a bad
row should stop the run, not quietly drop out of the metrics.
"""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from io import StringIO
from os import PathLike
from typing import BinaryIO, TextIO

import numpy as np
import pandas as pd

SCENARIOS = ("baseline", "normal", "stress")
KEY = ["entity_id", "as_of", "horizon", "scenario"]
STATE_PREFIX = "p_state_"
# columns that belong in one file only (p_state_* columns are predictions too)
PREDICTION_COLUMNS = ("p_event", "from_state")
OUTCOME_COLUMNS = ("event", "next_state")
# If the states include this one, the binary event is "in this state at the
# horizon" (default is absorbing), so p_event must equal p_state_default and
# event must equal next_state == "default".
EVENT_STATE = "default"
TOLERANCE = 1e-6
MAX_HORIZON = 2**63 - 1


class ContractError(ValueError):
    pass


def _require(df, cols, name):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ContractError(f"{name} is missing columns: {missing}")


def state_columns(predictions: pd.DataFrame) -> list[str]:
    return [c for c in predictions.columns if c.startswith(STATE_PREFIX)]


def _check_column_placement(predictions, outcomes):
    misplaced = [c for c in outcomes.columns if c in PREDICTION_COLUMNS] + state_columns(outcomes)
    if misplaced:
        raise ContractError(f"outcomes has prediction columns {misplaced}; they go in predictions")
    misplaced = [c for c in predictions.columns if c in OUTCOME_COLUMNS]
    if misplaced:
        raise ContractError(f"predictions has outcome columns {misplaced}; they go in outcomes")
    shared = sorted((set(predictions.columns) & set(outcomes.columns)) - set(KEY))
    if shared:
        raise ContractError(f"columns {shared} are in both files; only the key may be shared")


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _iso_date(value):
    """The value as a YYYY-MM-DD string, or None if it is not a real calendar date."""
    if isinstance(value, (dt.datetime, dt.date)):  # includes pandas Timestamp
        return value.date().isoformat() if isinstance(value, dt.datetime) else value.isoformat()
    text = str(value).strip()
    if not _ISO_DATE.fullmatch(text):
        return None
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _check_as_of(df, name):
    bad = [str(v) for v in df["as_of"] if _iso_date(v) is None]
    if bad:
        raise ContractError(
            f"{name} has as_of values that are not real dates in YYYY-MM-DD form: "
            f"{sorted(set(bad))[:5]}"
        )


def _horizon(value):
    """Exact positive int64 months, or None for an invalid horizon."""
    if isinstance(value, (bool, np.bool_, dt.date)):
        return None
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return None
        numerator, denominator = value.as_integer_ratio()
        return numerator if denominator == 1 and 1 <= numerator <= MAX_HORIZON else None
    text = str(value).strip()
    if "_" in text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if (
        not number.is_finite()
        or not 1 <= number <= MAX_HORIZON
        or number != number.to_integral_value()
    ):
        return None
    return int(number)


def _check_horizon(df, name):
    bad = df.loc[df["horizon"].map(_horizon).isna(), "horizon"]
    if len(bad):
        examples = sorted({str(v) for v in bad})[:5]
        raise ContractError(
            f"{name} has horizons that are not whole months in [1, {MAX_HORIZON}]: {examples}"
        )


def _normalise_key(df):
    # only called on validated frames, so every horizon converts cleanly;
    # this lets 12, 12.0 and "12" match across the two files
    return df.assign(
        entity_id=df["entity_id"].astype(str),
        as_of=df["as_of"].map(_iso_date),
        horizon=df["horizon"].map(_horizon).astype("int64"),
    )


def validate(predictions: pd.DataFrame, outcomes: pd.DataFrame) -> None:
    _require(predictions, KEY + ["p_event"], "predictions")
    _require(outcomes, KEY + ["event"], "outcomes")
    _check_column_placement(predictions, outcomes)

    for name, df in (("predictions", predictions), ("outcomes", outcomes)):
        if df[KEY].isna().any().any():
            raise ContractError(f"{name} has missing values in key columns")
        bad = sorted(set(df["scenario"]) - set(SCENARIOS))
        if bad:
            raise ContractError(f"{name} has unknown scenario labels: {bad}")
        _check_as_of(df, name)
        _check_horizon(df, name)
        # after canonicalising, so 12 and "12.0", or two spellings of one date, collide
        dupes = _normalise_key(df[KEY]).duplicated(KEY)
        if dupes.any():
            raise ContractError(f"{name} has {int(dupes.sum())} duplicate rows on {KEY}")

    p = pd.to_numeric(predictions["p_event"], errors="coerce")
    if np.iscomplexobj(p.to_numpy()):
        raise ContractError("p_event values must be real probabilities in [0, 1]")
    if p.isna().any():
        raise ContractError("p_event has missing or non-numeric values")
    if ((p < 0) | (p > 1)).any():
        raise ContractError("p_event values must be in [0, 1]")

    if outcomes["event"].map(lambda v: isinstance(v, (bool, np.bool_))).any():
        raise ContractError("event must be 0 or 1, not boolean True/False")
    if not outcomes["event"].isin([0, 1]).all():
        raise ContractError("event must be 0 or 1")

    if "from_state" in predictions.columns and predictions["from_state"].isna().any():
        raise ContractError("from_state has missing values")

    states = state_columns(predictions)
    if states:
        if "next_state" not in outcomes.columns:
            raise ContractError("p_state_* columns given but outcomes has no next_state")
        sp = predictions[states].apply(pd.to_numeric, errors="coerce")
        if np.iscomplexobj(sp.to_numpy()):
            raise ContractError("p_state_* values must be real probabilities in [0, 1]")
        if sp.isna().any().any() or ((sp < 0) | (sp > 1)).any().any():
            raise ContractError("p_state_* values must be numeric and in [0, 1]")
        if ((sp.sum(axis=1) - 1).abs() > TOLERANCE).any():
            raise ContractError("p_state_* columns must sum to 1 on every row")
        missing = int(outcomes["next_state"].isna().sum())
        if missing:
            raise ContractError(f"next_state is missing on {missing} rows")
        known = {c[len(STATE_PREFIX) :] for c in states}
        unknown = sorted(set(outcomes["next_state"].astype(str)) - known)
        if unknown:
            raise ContractError(f"next_state values without a p_state_ column: {unknown}")
        if EVENT_STATE in known:
            _check_event_matches_state(p, sp[STATE_PREFIX + EVENT_STATE], outcomes)


def _check_event_matches_state(p_event, p_state, outcomes):
    gap = (p_event - p_state).abs()
    if (gap > TOLERANCE).any():
        raise ContractError(
            f"p_event differs from {STATE_PREFIX}{EVENT_STATE} on {int((gap > TOLERANCE).sum())} "
            f"rows (largest gap {gap.max():.6f}); with a '{EVENT_STATE}' state the binary event "
            "is being in that state at the horizon, so the two must agree"
        )
    in_state = outcomes["next_state"].astype(str) == EVENT_STATE
    mismatch = int(((outcomes["event"] == 1) != in_state).sum())
    if mismatch:
        raise ContractError(
            f"event disagrees with next_state == '{EVENT_STATE}' on {mismatch} rows"
        )


def load(
    predictions_path: str | PathLike | BinaryIO | TextIO,
    outcomes_path: str | PathLike | BinaryIO | TextIO,
) -> pd.DataFrame:
    # Keep raw horizon text so CSV inference cannot round large integers via float64.
    text = {"entity_id": str, "as_of": str, "horizon": str, "from_state": str, "next_state": str}
    predictions = _read_csv(predictions_path, "predictions", text)
    outcomes = _read_csv(outcomes_path, "outcomes", text)
    return join(predictions, outcomes)


def _read_csv(source, name, text):
    # read_csv's handle adapter (under the pinned pandas version) preserves
    # existing path/stream decoding and inferred compression. Freeze its text
    # so header validation and data parsing cannot observe different inputs.
    with pd.io.common.get_handle(
        source, "r", encoding="utf-8", compression="infer", is_text=True
    ) as h:
        snapshot = StringIO(h.handle.read())
    # header=None exposes original names before pandas silently renames
    # duplicates. Reuse its CSV parser for quoted names, BOMs and blank lines.
    header = pd.read_csv(snapshot, header=None, nrows=1, dtype=str, keep_default_na=False).iloc[0]
    duplicates = sorted(set(header[header.duplicated()].tolist()))
    if duplicates:
        raise ContractError(f"{name} has duplicate CSV column names: {duplicates}")
    snapshot.seek(0)
    # Only empty fields are missing; NA/NULL/nan remain valid string labels.
    # Round-trip parsing keeps forecasts exactly on k/n_bins in their bin.
    return pd.read_csv(
        snapshot, dtype=text, keep_default_na=False, na_values=[""], float_precision="round_trip"
    )


def join(predictions: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    validate(predictions, outcomes)
    predictions, outcomes = _normalise_key(predictions), _normalise_key(outcomes)
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
    if state_columns(merged):
        merged["next_state"] = merged["next_state"].astype(str)
    return merged
