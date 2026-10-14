"""Leakage checks for a split panel.

Each check returns {"status": "pass" | "fail" | "skipped", ...details}.
`run_checks` bundles them with the split manifest into one JSON-friendly
report.
"""

import hashlib
import json

import numpy as np
import pandas as pd

from panel import PanelSpec
from splits import DROP, SPLITS


def _result(failed: bool, **details) -> dict:
    return {"status": "fail" if failed else "pass", **details}


def _skipped(reason: str) -> dict:
    return {"status": "skipped", "reason": reason}


def check_entity_overlap(df, labels, spec: PanelSpec) -> dict:
    kept = labels != DROP
    splits_per_entity = labels[kept].groupby(df.loc[kept, spec.entity_col]).nunique()
    shared = sorted(splits_per_entity[splits_per_entity > 1].index.astype(str))
    return _result(bool(shared), entities=shared[:20], n_entities=len(shared))


def trajectory_hashes(df, labels, spec: PanelSpec, decimals: int = 2) -> pd.DataFrame:
    """Hash each (entity, split) feature trajectory after z-scoring and rounding.

    Two trajectories with the same hash are near duplicates: same shape over
    the same number of steps, ignoring tiny noise and the entity id. Absolute
    dates are not part of the hash, so a copy shifted in time still matches.
    """
    kept = labels != DROP
    feats = df.loc[kept, spec.feature_cols].astype(float)
    std = feats.std(ddof=0).replace(0, 1.0)
    z = ((feats - feats.mean()) / std).round(decimals).fillna(np.inf)
    z = z + 0.0  # turn -0.0 into 0.0 so it hashes like 0.0
    frame = z.assign(
        _entity=df.loc[kept, spec.entity_col].astype(str),
        _time=df.loc[kept, spec.time_col],
        _split=labels[kept],
    ).sort_values(["_entity", "_time"])

    rows = []
    for (entity, split), part in frame.groupby(["_entity", "_split"], sort=True):
        values = np.ascontiguousarray(part[spec.feature_cols].to_numpy())
        digest = hashlib.sha256(values.tobytes()).hexdigest()
        rows.append({"entity": entity, "split": split, "hash": digest})
    return pd.DataFrame(rows)


def check_near_duplicates(df, labels, spec: PanelSpec, decimals: int = 2) -> dict:
    hashes = trajectory_hashes(df, labels, spec, decimals)
    pairs = []
    for _, group in hashes.groupby("hash"):
        if group["split"].nunique() > 1:
            pairs.append(sorted(zip(group["entity"], group["split"])))
    return _result(
        bool(pairs), groups=pairs[:20], n_groups=len(pairs), decimals=decimals
    )


def check_time_order(df, labels, spec: PanelSpec) -> dict:
    times = df[spec.time_col]
    bounds = {
        s: (times[labels == s].min(), times[labels == s].max())
        for s in SPLITS
        if (labels == s).any()
    }
    violations = []
    for i, earlier in enumerate(SPLITS):
        for later in SPLITS[i + 1 :]:
            if earlier not in bounds or later not in bounds:
                continue
            last_outcome = bounds[earlier][1] + spec.horizon
            first_later = bounds[later][0]
            if last_outcome > first_later:
                violations.append(
                    {
                        "earlier": earlier,
                        "later": later,
                        "earlier_max_time_plus_horizon": last_outcome.isoformat(),
                        "later_min_time": first_later.isoformat(),
                    }
                )
    return _result(bool(violations), violations=violations)


def check_feature_timestamps(df, labels, spec: PanelSpec) -> dict:
    if not spec.observed_at:
        return _skipped("no observed_at columns declared")
    kept = labels != DROP
    late = {}
    for feature, col in spec.observed_at.items():
        n = int((df.loc[kept, col] > df.loc[kept, spec.time_col]).sum())
        if n:
            late[feature] = n
    return _result(bool(late), rows_observed_after_prediction_time=late)


def check_post_outcome_fields(df, labels, spec: PanelSpec) -> dict:
    banned = set(spec.post_outcome_cols) | {spec.target_col}
    bad = [c for c in spec.feature_cols if c in banned]
    return _result(bool(bad), features=bad)


def _auc(score: pd.Series, y: pd.Series) -> float:
    ranks = score.rank()
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def check_target_leakage(
    df,
    labels,
    spec: PanelSpec,
    threshold: float = 0.99,
    max_shift: int = 3,
    min_rows: int = 30,
) -> dict:
    """Flag features that look like the target in disguise.

    Two sniffs per numeric feature:
      * the feature equals the target, or the target of a later row of the
        same entity (shift 1..max_shift), on >= threshold of rows;
      * the feature alone separates the target almost perfectly
        (AUC for a binary target, rank correlation otherwise).
    This catches copies and near copies. It will not catch subtle leaks.
    """
    kept = labels != DROP
    data = df.loc[kept].sort_values([spec.entity_col, spec.time_col])
    y = data[spec.target_col]
    binary = bool(y.dropna().isin([0, 1]).all())
    by_entity = data.groupby(spec.entity_col)[spec.target_col]
    suspects = []

    for col in spec.feature_cols:
        if not pd.api.types.is_numeric_dtype(data[col]):
            continue
        x = data[col].astype(float)
        if x.nunique(dropna=True) < 2:
            continue

        for shift in range(max_shift + 1):
            target = by_entity.shift(-shift)
            both = x.notna() & target.notna()
            if both.sum() < min_rows:
                continue
            match = np.isclose(x[both], target[both].astype(float)).mean()
            if match >= threshold:
                suspects.append(
                    {
                        "feature": col,
                        "reason": "equals_target",
                        "shift": shift,
                        "match_rate": round(float(match), 4),
                    }
                )
                break

        both = x.notna() & y.notna()
        if both.sum() < min_rows:
            continue
        if binary:
            yb = y[both].astype(int)
            if yb.nunique() < 2:
                continue
            auc = _auc(x[both], yb)
            score = max(auc, 1 - auc)
            metric = "auc"
        else:
            score = abs(x[both].rank().corr(y[both].astype(float).rank()))
            metric = "abs_rank_corr"
        if score >= threshold:
            suspects.append(
                {
                    "feature": col,
                    "reason": "near_perfect_predictor",
                    metric: round(float(score), 4),
                }
            )

    return _result(bool(suspects), suspects=suspects, threshold=threshold)


def run_checks(df, labels, spec: PanelSpec, manifest: dict) -> dict:
    checks = {}
    if manifest.get("entity_disjoint"):
        checks["entity_overlap"] = check_entity_overlap(df, labels, spec)
        checks["near_duplicate_trajectories"] = check_near_duplicates(df, labels, spec)
    else:
        reason = "policy allows the same entity in several splits"
        checks["entity_overlap"] = _skipped(reason)
        checks["near_duplicate_trajectories"] = _skipped(reason)
    if manifest.get("time_ordered"):
        checks["time_order"] = check_time_order(df, labels, spec)
    else:
        checks["time_order"] = _skipped("policy does not split by time")
    checks["feature_timestamps"] = check_feature_timestamps(df, labels, spec)
    checks["post_outcome_fields"] = check_post_outcome_fields(df, labels, spec)
    checks["target_leakage"] = check_target_leakage(df, labels, spec)

    failed = [name for name, c in checks.items() if c["status"] == "fail"]
    return {"ok": not failed, "failed": failed, "checks": checks, "manifest": manifest}


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, default=str)
