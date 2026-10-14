"""Train / valid / test split generator for panel data.

Policies:
  time         out-of-time split with a purge gap of horizon + embargo
               before each later split. Entities may appear in several splits.
  entity       entities are shuffled with a seed and assigned whole to one
               split. Time is ignored.
  time_entity  both: a row is kept only if its time window and its entity
               group agree. Strictest option.

Rows that fall in a purge gap (or in the wrong entity group) get the label
"drop" and should not be used for training or scoring.
"""

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from panel import PanelSpec

SPLITS = ("train", "valid", "test")
DROP = "drop"
POLICIES = ("time", "entity", "time_entity")


@dataclass
class SplitResult:
    labels: pd.Series
    manifest: dict


def _time_labels(times, valid_start, test_start, horizon, embargo) -> pd.Series:
    labels = pd.Series(DROP, index=times.index, dtype=object)
    # A row's outcome window (plus embargo) must close before the next split starts.
    window_end = times + horizon + embargo
    labels[window_end <= valid_start] = "train"
    labels[(times >= valid_start) & (window_end <= test_start)] = "valid"
    labels[times >= test_start] = "test"
    return labels


def _entity_groups(entities: pd.Series, fractions, seed: int) -> dict:
    uniq = np.array(sorted(entities.unique()))
    order = np.random.default_rng(seed).permutation(len(uniq))
    n_train = round(fractions[0] * len(uniq))
    n_valid = round(fractions[1] * len(uniq))
    groups = {}
    for rank, idx in enumerate(order):
        if rank < n_train:
            groups[uniq[idx]] = "train"
        elif rank < n_train + n_valid:
            groups[uniq[idx]] = "valid"
        else:
            groups[uniq[idx]] = "test"
    return groups


def assignment_hash(df: pd.DataFrame, labels: pd.Series, spec: PanelSpec) -> str:
    keyed = pd.DataFrame(
        {
            "e": df[spec.entity_col].astype(str),
            "t": df[spec.time_col].dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "s": labels.astype(str),
        }
    ).sort_values(["e", "t"])
    payload = "\n".join(keyed["e"] + "|" + keyed["t"] + "|" + keyed["s"])
    return hashlib.sha256(payload.encode()).hexdigest()


def make_splits(
    df: pd.DataFrame,
    spec: PanelSpec,
    policy: str,
    *,
    valid_start=None,
    test_start=None,
    embargo: pd.Timedelta | None = None,
    fractions=(0.7, 0.15, 0.15),
    seed: int = 0,
) -> SplitResult:
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}, expected one of {POLICIES}")
    spec.validate(df)
    if embargo is None:
        embargo = pd.Timedelta(0)

    uses_time = policy in ("time", "time_entity")
    uses_entity = policy in ("entity", "time_entity")

    if uses_time:
        if valid_start is None or test_start is None:
            raise ValueError(f"policy {policy!r} needs valid_start and test_start")
        valid_start, test_start = pd.Timestamp(valid_start), pd.Timestamp(test_start)
        if valid_start >= test_start:
            raise ValueError("valid_start must be before test_start")
        time_labels = _time_labels(
            df[spec.time_col], valid_start, test_start, spec.horizon, embargo
        )
    if uses_entity:
        if len(fractions) != 3 or abs(sum(fractions) - 1) > 1e-9:
            raise ValueError("fractions must be three numbers summing to 1")
        groups = _entity_groups(df[spec.entity_col], fractions, seed)
        entity_labels = df[spec.entity_col].map(groups)

    if policy == "time":
        labels = time_labels
    elif policy == "entity":
        labels = entity_labels.astype(object)
    else:
        labels = time_labels.where(time_labels == entity_labels, DROP)
    labels = labels.rename("split")

    kept = labels != DROP
    manifest = {
        "policy": policy,
        "seed": seed if uses_entity else None,
        "fractions": list(fractions) if uses_entity else None,
        "valid_start": valid_start.isoformat() if uses_time else None,
        "test_start": test_start.isoformat() if uses_time else None,
        "horizon": str(spec.horizon),
        "embargo": str(embargo) if uses_time else None,
        "entity_disjoint": uses_entity,
        "time_ordered": uses_time,
        "rows": {s: int((labels == s).sum()) for s in (*SPLITS, DROP)},
        "entities": {
            s: int(df.loc[labels == s, spec.entity_col].nunique()) for s in SPLITS
        },
        "rows_kept": int(kept.sum()),
        "assignment_sha256": assignment_hash(df, labels, spec),
        "spec": spec.describe(),
    }
    return SplitResult(labels=labels, manifest=manifest)
