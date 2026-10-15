"""Train / valid / test split generator for panel data.

Policies:
  time         out-of-time split with a purge gap of horizon + embargo
               before each later split. Entities may appear in several splits.
  entity       each entity is assigned whole to one split by a seeded hash of
               its id. Time is ignored.
  time_entity  both: a row is kept only if its time window and its entity
               group agree. Strictest option.

Rows that fall in a purge gap (or in the wrong entity group) get the label
"drop" and should not be used for training or scoring. A split that would
end up with no rows is an error, not an empty result.
"""

import hashlib
import json
import math
from dataclasses import dataclass

import pandas as pd

from panel import PanelSpec, horizon_ends

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
    try:
        window_end = horizon_ends(times, horizon) + embargo
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("horizon plus embargo must be finite on every row") from exc
    if window_end.isna().any():
        raise ValueError("horizon plus embargo must be finite on every row")
    labels[window_end <= valid_start] = "train"
    labels[(times >= valid_start) & (window_end <= test_start)] = "valid"
    labels[times >= test_start] = "test"
    return labels


def _check_fractions(fractions) -> tuple[float, float, float]:
    try:
        values = tuple(float(f) for f in fractions)
    except (TypeError, ValueError):
        raise ValueError("fractions must be three numbers summing to 1") from None
    if (
        len(values) != 3
        or not all(math.isfinite(f) and f > 0 for f in values)
        or abs(sum(values) - 1) > 1e-9
    ):
        raise ValueError(
            f"fractions must be three positive numbers summing to 1, got {fractions}"
        )
    return values


def entity_bucket(entity, seed: int) -> float:
    """Map an entity id to a number in [0, 1) using sha256 of "seed:id".

    The value depends only on the seed and the id itself, so adding or
    removing other entities never moves an entity to another split.
    """
    digest = hashlib.sha256(f"{seed}:{entity}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _entity_groups(entities: pd.Series, fractions, seed: int) -> dict:
    train_cut = fractions[0]
    valid_cut = fractions[0] + fractions[1]
    groups = {}
    for entity in entities.unique():
        u = entity_bucket(entity, seed)
        if u < train_cut:
            groups[entity] = "train"
        elif u < valid_cut:
            groups[entity] = "valid"
        else:
            groups[entity] = "test"
    return groups


def assignment_hash(df: pd.DataFrame, labels: pd.Series, spec: PanelSpec) -> str:
    # JSON escapes delimiters inside ids; joining pipe/newline-delimited
    # triples lets one id imitate several rows. Preserve native id types,
    # all nine fractional digits and the UTC offset as well.
    records = [
        [
            f"{type(entity).__module__}.{type(entity).__qualname__}",
            str(entity),
            timestamp.isoformat(timespec="nanoseconds"),
            str(label),
        ]
        for entity, timestamp, label in zip(
            df[spec.entity_col], df[spec.time_col], labels, strict=True
        )
    ]
    payload = json.dumps(sorted(records), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _cutoff(value, name: str, times: pd.Series) -> pd.Timestamp:
    try:
        ts = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite timestamp") from exc
    if pd.isna(ts):
        raise ValueError(f"{name} must be a finite timestamp")
    if (ts.tz is None) != (times.dt.tz is None):
        raise ValueError(
            f"{name} ({ts}) and the timestamps ({times.dtype}) must both be "
            "timezone-aware or both naive"
        )
    return ts


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
    if (
        not isinstance(embargo, pd.Timedelta)
        or pd.isna(embargo)
        or embargo < pd.Timedelta(0)
    ):
        raise ValueError("embargo must be a nonnegative finite Timedelta")

    uses_time = policy in ("time", "time_entity")
    uses_entity = policy in ("entity", "time_entity")

    if uses_time:
        if valid_start is None or test_start is None:
            raise ValueError(f"policy {policy!r} needs valid_start and test_start")
        times = df[spec.time_col]
        valid_start = _cutoff(valid_start, "valid_start", times)
        test_start = _cutoff(test_start, "test_start", times)
        if valid_start >= test_start:
            raise ValueError("valid_start must be before test_start")
        time_labels = _time_labels(
            times, valid_start, test_start, spec.horizon, embargo
        )
    if uses_entity:
        fractions = _check_fractions(fractions)
        groups = _entity_groups(df[spec.entity_col], fractions, seed)
        entity_labels = df[spec.entity_col].map(groups)

    if policy == "time":
        labels = time_labels
    elif policy == "entity":
        labels = entity_labels.astype(object)
    else:
        labels = time_labels.where(time_labels == entity_labels, DROP)
    labels = labels.rename("split")

    rows = {s: int((labels == s).sum()) for s in (*SPLITS, DROP)}
    empty = [s for s in SPLITS if rows[s] == 0]
    if empty:
        detail = f"rows per split: {rows}"
        if uses_entity:
            per_group = {s: list(groups.values()).count(s) for s in SPLITS}
            detail += f"; entities per group: {per_group}"
        raise ValueError(
            f"split(s) {empty} would be empty ({detail}). Use more entities, "
            "other fractions or seed, or move the cutoffs."
        )

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
        "rows": rows,
        "entities": {
            s: int(df.loc[labels == s, spec.entity_col].nunique()) for s in SPLITS
        },
        "rows_kept": int(kept.sum()),
        "assignment_sha256": assignment_hash(df, labels, spec),
        "spec": spec.describe(),
    }
    return SplitResult(labels=labels, manifest=manifest)
