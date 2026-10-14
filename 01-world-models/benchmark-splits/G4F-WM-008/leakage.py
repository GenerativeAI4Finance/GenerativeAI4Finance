"""Leakage checks for a split panel.

Each check returns {"status": "pass" | "fail" | "skipped", ...details}.
`run_checks` bundles them with the split manifest into one JSON-friendly
report.
"""

import hashlib
import json
import math

import numpy as np
import pandas as pd

from panel import PanelSpec
from splits import DROP, SPLITS


def _result(failed: bool, **details) -> dict:
    return {"status": "fail" if failed else "pass", **details}


def _skipped(reason: str, **details) -> dict:
    return {"status": "skipped", "reason": reason, **details}


def _numeric_features(df, spec: PanelSpec) -> tuple[list[str], dict]:
    numeric, ignored = [], {}
    for col in spec.feature_cols:
        if pd.api.types.is_numeric_dtype(df[col]):
            numeric.append(col)
        else:
            ignored[col] = "not numeric"
    return numeric, ignored


def check_split_sizes(df, labels, spec: PanelSpec) -> dict:
    rows = {s: int((labels == s).sum()) for s in SPLITS}
    empty = [s for s in SPLITS if rows[s] == 0]
    return _result(bool(empty), rows=rows, empty=empty)


def check_entity_overlap(df, labels, spec: PanelSpec) -> dict:
    kept = labels != DROP
    splits_per_entity = labels[kept].groupby(df.loc[kept, spec.entity_col]).nunique()
    if splits_per_entity.empty:
        return _skipped("no rows are labelled train, valid or test", entities_checked=0)
    shared = sorted(splits_per_entity[splits_per_entity > 1].index.astype(str))
    return _result(
        bool(shared),
        entities=shared[:20],
        n_entities=len(shared),
        entities_checked=len(splits_per_entity),
    )


def _entity_trajectories(df, labels, spec: PanelSpec, features) -> dict:
    """Whole feature history of every entity that has kept rows.

    Values are z-scored with the mean and std of the whole panel and rows
    are in time order. Rows labelled drop are included: under time_entity a
    copy of an entity keeps rows in a different time window from the
    original, so comparing only kept rows would never match them.
    """
    feats = df[features].astype(float)
    z = ((feats - feats.mean()) / feats.std(ddof=0)).reset_index(drop=True)
    z["_entity"] = df[spec.entity_col].astype(str).to_numpy()
    z["_time"] = df[spec.time_col].reset_index(drop=True)
    z["_split"] = labels.to_numpy()
    z = z.sort_values(["_entity", "_time"], kind="stable")

    out = {}
    for entity, part in z.groupby("_entity", sort=True):
        splits = sorted(set(part["_split"]) - {DROP})
        if splits:
            out[entity] = ("+".join(splits), part[features].to_numpy())
    return out


def _summary(z: np.ndarray, segments: int = 4) -> np.ndarray:
    """Fixed-length summary of a trajectory, used to pick candidate pairs:
    per feature, five quantiles and the means of `segments` stretches of
    the history in time order."""
    z = np.nan_to_num(z, nan=0.0)
    if len(z) < segments:
        z = np.repeat(z, segments, axis=0)
    quantiles = np.quantile(z, (0.1, 0.25, 0.5, 0.75, 0.9), axis=0).ravel()
    means = np.concatenate([part.mean(axis=0) for part in np.array_split(z, segments)])
    return np.concatenate([quantiles, means])


def _nearest(points: np.ndarray, k: int, chunk: int = 512) -> np.ndarray:
    """Indices of the k nearest other points (Euclidean) for every point,
    computed in blocks so memory stays at chunk * len(points)."""
    k = min(k, len(points) - 1)
    sq = (points**2).sum(axis=1)
    out = np.empty((len(points), k), dtype=int)
    for start in range(0, len(points), chunk):
        block = slice(start, start + chunk)
        d2 = sq[block, None] + sq[None, :] - 2 * points[block] @ points.T
        d2[np.arange(d2.shape[0]), np.arange(start, start + d2.shape[0])] = np.inf
        out[block] = np.argpartition(d2, k - 1, axis=1)[:, :k]
    return out


def _row_costs(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # A missing value against a present one counts as 1 std apart.
    d2 = (a - b) ** 2
    na, nb = np.isnan(a), np.isnan(b)
    d2[na & nb] = 0.0
    d2[na ^ nb] = 1.0
    return d2.mean(axis=1)


def align_trajectories(a, b, max_skip: int, gap: float = 1.0):
    """Align two z-scored trajectories (rows in time order).

    Rows are matched in order; up to `max_skip` rows of either trajectory
    may be left unmatched, at a cost of `gap` each. Returns
    (rms, unmatched_rows), where rms is the root mean squared difference
    over the matched rows, or None if the lengths differ by more than
    max_skip.
    """
    n, m = len(a), len(b)
    if abs(n - m) > max_skip:
        return None
    width = 2 * max_skip + 1
    # cost[i][k]: row i of a against row i + k - max_skip of b.
    cost = [[math.inf] * width for _ in range(n)]
    for k in range(width):
        d = k - max_skip
        lo, hi = max(0, -d), min(n, m - d)
        if hi > lo:
            for i, c in enumerate(_row_costs(a[lo:hi], b[lo + d : hi + d]), start=lo):
                cost[i][k] = float(c)

    # best[k] = (total cost, unmatched rows) for prefixes a[:i], b[:i + k - max_skip]
    prev = None
    for i in range(n + 1):
        best = [(math.inf, 0)] * width
        for k in range(width):
            j = i + k - max_skip
            if j < 0 or j > m:
                continue
            if i == 0 and j == 0:
                best[k] = (0.0, 0)
                continue
            options = []
            if i > 0 and j > 0:
                total, skipped = prev[k]
                options.append((total + cost[i - 1][k], skipped))
            if i > 0 and k + 1 < width:
                total, skipped = prev[k + 1]
                options.append((total + gap, skipped + 1))
            if j > 0 and k > 0:
                total, skipped = best[k - 1]
                options.append((total + gap, skipped + 1))
            best[k] = min(options)
        prev = best

    total, skipped = prev[m - n + max_skip]
    matched = (n + m - skipped) / 2
    if matched == 0 or math.isinf(total):
        return None
    return math.sqrt(max(total - gap * skipped, 0.0) / matched), skipped


def check_near_duplicates(
    df,
    labels,
    spec: PanelSpec,
    tolerance: float = 0.1,
    max_missing_frac: float = 0.05,
    min_distinct_rows: int = 5,
    n_neighbors: int = 10,
    decimals: int = 2,
) -> dict:
    """Find entities in different splits whose feature histories are near copies.

    Each entity's whole history is z-scored with the panel's mean and std.
    Candidate pairs are entities with identical histories after rounding to
    `decimals`, plus each entity's `n_neighbors` nearest entities by a
    fixed-length trajectory summary. A candidate pair in different splits is
    a near duplicate when its rows, aligned in time order with up to
    `max_missing_frac` of rows (at least one) unmatched, differ by at most
    `tolerance` standard deviations (root mean square over matched rows).
    Absolute dates are ignored, so a copy shifted in time still matches.

    Entities with fewer than `min_distinct_rows` distinct rows (dormant or
    very short histories) are not compared, because unrelated entities look
    the same there. They are counted under low_information.
    """
    features, ignored = _numeric_features(df, spec)
    std = df[features].astype(float).std(ddof=0)
    for col in features:
        if not std[col] > 0:
            ignored[col] = "constant across the panel"
    features = [c for c in features if c not in ignored]
    if not features:
        return _skipped(
            "no numeric feature varies across the panel", ignored_features=ignored
        )

    trajectories = _entity_trajectories(df, labels, spec, features)
    compared, low_info, digests = [], [], {}
    for entity, (_, z) in trajectories.items():
        rounded = np.where(np.isnan(z), np.inf, np.round(z, decimals) + 0.0)
        if len(np.unique(rounded, axis=0)) < min_distinct_rows:
            low_info.append(entity)
            continue
        compared.append(entity)
        digests[entity] = hashlib.sha256(rounded.tobytes()).hexdigest()

    low_information = {"n_entities": len(low_info), "entities": low_info[:20]}
    if len(compared) < 2:
        return _skipped(
            "fewer than 2 entities have enough distinct rows to compare",
            compared_entities=len(compared),
            low_information=low_information,
            ignored_features=ignored,
        )

    candidates = set()
    by_digest = {}
    for entity, digest in digests.items():
        by_digest.setdefault(digest, []).append(entity)
    for group in by_digest.values():
        candidates.update((a, b) for i, a in enumerate(group) for b in group[i + 1 :])
    summaries = np.array([_summary(trajectories[e][1]) for e in compared])
    for i, row in enumerate(_nearest(summaries, n_neighbors)):
        for j in row:
            candidates.add(tuple(sorted((compared[i], compared[j]))))

    pairs = []
    for a, b in sorted(candidates):
        (split_a, za), (split_b, zb) = trajectories[a], trajectories[b]
        if split_a == split_b:
            continue
        max_skip = max(1, int(max_missing_frac * max(len(za), len(zb))))
        aligned = align_trajectories(za, zb, max_skip)
        if aligned is None:
            continue
        rms, unmatched = aligned
        if rms <= tolerance and unmatched <= max_skip:
            pairs.append(
                {
                    "entities": [(a, split_a), (b, split_b)],
                    "match": "exact" if digests[a] == digests[b] else "near",
                    "rms": round(rms, 4),
                    "unmatched_rows": unmatched,
                }
            )
    return _result(
        bool(pairs),
        pairs=pairs[:20],
        n_pairs=len(pairs),
        compared_entities=len(compared),
        low_information=low_information,
        ignored_features=ignored,
        tolerance=tolerance,
    )


def check_time_order(df, labels, spec: PanelSpec) -> dict:
    times = df[spec.time_col]
    bounds = {
        s: (times[labels == s].min(), times[labels == s].max())
        for s in SPLITS
        if (labels == s).any()
    }
    if len(bounds) < 2:
        return _skipped("fewer than 2 splits have rows", splits_with_rows=len(bounds))
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
    """A feature value must be known by the row's prediction time.

    Per declared feature, over kept rows that hold a feature value:
    `late` counts rows whose observed_at is after the prediction time and
    `unknown` counts rows with no observed_at, which cannot be shown to be
    on time. Either one fails the check. Skipped when no declared feature
    has a value on a kept row.
    """
    if not spec.observed_at:
        return _skipped("no observed_at columns declared")
    kept = (labels != DROP).to_numpy()
    coverage, failed = {}, False
    for feature, col in spec.observed_at.items():
        has_value = kept & df[feature].notna().to_numpy()
        seen = df[col]
        unknown = has_value & seen.isna().to_numpy()
        late = has_value & ~unknown & (seen > df[spec.time_col]).to_numpy()
        coverage[feature] = {
            "rows_checked": int(has_value.sum() - unknown.sum()),
            "late": int(late.sum()),
            "unknown": int(unknown.sum()),
        }
        failed |= bool(late.any() or unknown.any())
    if not failed and not any(c["rows_checked"] for c in coverage.values()):
        return _skipped("no kept row has a feature value to check", features=coverage)
    return _result(failed, features=coverage)


def check_post_outcome_fields(
    df,
    labels,
    spec: PanelSpec,
    min_positives: int = 10,
    min_positive_share: float = 0.5,
    max_negative_share: float = 0.001,
) -> dict:
    """Declared post-outcome columns (or the target) used as features, plus a
    value heuristic for undeclared ones.

    For a 0/1 target, a feature is suspect when it differs from its usual
    value (the most common value on negative rows, missing included) on at
    least `min_positive_share` of positive rows but on at most
    `max_negative_share` of negative rows: it is only ever set once the
    outcome has happened, like a collections flag or a recovery amount.
    """
    banned = set(spec.post_outcome_cols) | {spec.target_col}
    bad = [c for c in spec.feature_cols if c in banned]

    kept = np.ones(len(df), bool) if labels is None else (labels != DROP).to_numpy()
    y = df[spec.target_col].to_numpy(dtype=float)[kept]
    pos, neg = y == 1, y == 0
    suspects = []
    if not np.isin(y[~np.isnan(y)], (0, 1)).all():
        value_check = "skipped: target is not 0/1"
    elif min(pos.sum(), neg.sum()) < min_positives:
        value_check = (
            f"skipped: {int(pos.sum())} positive and {int(neg.sum())} negative "
            f"rows, need {min_positives} of each"
        )
    elif not any(df[c][kept].notna().any() for c in spec.feature_cols):
        value_check = "skipped: no feature has a value on a kept row"
    else:
        value_check = "ran"
        for col in spec.feature_cols:
            if col in bad:
                continue
            x = df[col][kept].reset_index(drop=True)
            usual = x[neg].mode(dropna=False).iloc[0]
            is_set = (x.notna() if pd.isna(usual) else x.ne(usual)).to_numpy()
            pos_share, neg_share = is_set[pos].mean(), is_set[neg].mean()
            if pos_share >= min_positive_share and neg_share <= max_negative_share:
                suspects.append(
                    {
                        "feature": col,
                        "reason": "only_set_when_target_positive",
                        "share_of_positive_rows": round(float(pos_share), 4),
                        "share_of_negative_rows": round(float(neg_share), 4),
                    }
                )
    return _result(
        bool(bad or suspects), features=bad, suspects=suspects, value_check=value_check
    )


def _auc(score: pd.Series, y: pd.Series) -> float:
    ranks = score.rank()
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _kappa(x: np.ndarray, y: np.ndarray) -> float:
    """Cohen's kappa for x == y. Chance agreement comes from how often each
    value occurs in x and in y, so two mostly-zero columns do not agree just
    by both being mostly zero."""
    observed = np.isclose(x, y).mean()
    px = pd.Series(np.round(x, 6)).value_counts(normalize=True)
    py = pd.Series(np.round(y, 6)).value_counts(normalize=True)
    chance = float((px * py).sum())
    if chance >= 1:
        return math.nan
    return float((observed - chance) / (1 - chance))


def _best_kappa(x, targets: dict, binary, min_rows, min_positives):
    best = None
    for shift, target in targets.items():
        both = (x.notna() & target.notna()).to_numpy()
        if both.sum() < min_rows:
            continue
        t = target.to_numpy()[both]
        if binary and min((t == 1).sum(), (t == 0).sum()) < min_positives:
            continue
        kappa = _kappa(x.to_numpy()[both], t)
        if not math.isnan(kappa) and (best is None or kappa > best[0]):
            best = (kappa, shift)
    return best


def check_target_leakage(
    df,
    labels,
    spec: PanelSpec,
    threshold: float = 0.99,
    copy_threshold: float = 0.85,
    max_shift: int = 3,
    max_lag: int = 12,
    min_rows: int = 30,
    min_positives: int = 10,
) -> dict:
    """Flag features that look like the target in disguise.

    Two sniffs per numeric feature:
      * copies_target: Cohen's kappa between the feature and a target it
        should not see is >= copy_threshold. Targets it should not see are
        this row's (shift 0), those of the next max_shift rows of the same
        entity (shift > 0), and those of up to max_lag earlier rows whose
        outcome window is still open at this row's time (shift < 0). A
        feature that agrees at least as well with an earlier target whose
        window has already closed is a legitimate lagged label and is not
        flagged.
      * near_perfect_predictor: the feature alone separates the target
        almost perfectly (AUC for a 0/1 target, rank correlation otherwise)
        at >= threshold.
    With fewer than min_rows labelled rows, or fewer than min_positives
    rows of either class for a 0/1 target, the check is skipped rather than
    passed. It catches copies and near copies, not subtle leaks.
    """
    kept = (labels != DROP).to_numpy()
    data = df.loc[kept].sort_values([spec.entity_col, spec.time_col])
    data = data.reset_index(drop=True)
    y = data[spec.target_col].astype(float)
    labelled = int(y.notna().sum())
    if labelled < min_rows:
        return _skipped(f"only {labelled} labelled rows, need {min_rows}")
    binary = bool(y.dropna().isin([0, 1]).all())
    if binary:
        n_pos, n_neg = int((y == 1).sum()), int((y == 0).sum())
        if min(n_pos, n_neg) < min_positives:
            return _skipped(
                f"{n_pos} positive and {n_neg} negative rows, "
                f"need {min_positives} of each"
            )
    elif y.nunique() < 2:
        return _skipped("target is constant")

    data["_y"] = y
    data["_window_end"] = data[spec.time_col] + spec.horizon
    by_entity = data.groupby(spec.entity_col, sort=False)
    unseen, seen = {}, {}
    for shift in range(max_shift + 1):
        unseen[shift] = by_entity["_y"].shift(-shift)
    for lag in range(1, max_lag + 1):
        earlier = by_entity["_y"].shift(lag)
        still_open = by_entity["_window_end"].shift(lag) > data[spec.time_col]
        unseen[-lag] = earlier.where(still_open)
        seen[-lag] = earlier.where(~still_open)

    suspects, skipped_features, evaluated = [], {}, []
    for col in spec.feature_cols:
        if not pd.api.types.is_numeric_dtype(data[col]):
            skipped_features[col] = "not numeric"
            continue
        x = data[col].astype(float)
        if x.nunique(dropna=True) < 2:
            skipped_features[col] = "constant"
            continue

        leak = _best_kappa(x, unseen, binary, min_rows, min_positives)
        legit = _best_kappa(x, seen, binary, min_rows, min_positives)
        if leak or legit:
            evaluated.append(col)
        if (
            leak
            and leak[0] >= copy_threshold
            and (legit is None or leak[0] >= legit[0])
        ):
            suspects.append(
                {
                    "feature": col,
                    "reason": "copies_target",
                    "shift": leak[1],
                    "kappa": round(leak[0], 4),
                }
            )

        both = x.notna() & y.notna()
        if both.sum() < min_rows:
            skipped_features[col] = f"fewer than {min_rows} rows with a value"
            continue
        if binary:
            yb = y[both].astype(int)
            if min(yb.sum(), len(yb) - yb.sum()) < min_positives:
                skipped_features[col] = f"fewer than {min_positives} rows of a class"
                continue
            auc = _auc(x[both], yb)
            score = max(auc, 1 - auc)
            metric = "auc"
        else:
            score = abs(x[both].rank().corr(y[both].rank()))
            metric = "abs_rank_corr"
        if col not in evaluated:
            evaluated.append(col)
        if score >= threshold:
            suspects.append(
                {
                    "feature": col,
                    "reason": "near_perfect_predictor",
                    metric: round(float(score), 4),
                }
            )

    if not evaluated:
        return _skipped(
            "no feature could be evaluated", skipped_features=skipped_features
        )
    return _result(
        bool(suspects),
        suspects=suspects,
        features_evaluated=evaluated,
        skipped_features=skipped_features,
        threshold=threshold,
        copy_threshold=copy_threshold,
    )


def _check_labels(df, labels) -> None:
    if not labels.index.equals(df.index):
        raise ValueError("labels must have the same index as df")
    unknown = set(labels.unique()) - {*SPLITS, DROP}
    if unknown:
        raise ValueError(f"unknown split labels: {sorted(map(str, unknown))}")


def run_checks(df, labels, spec: PanelSpec, manifest: dict) -> dict:
    spec.validate(df)
    _check_labels(df, labels)
    checks = {"split_sizes": check_split_sizes(df, labels, spec)}
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
    skipped = [name for name, c in checks.items() if c["status"] == "skipped"]
    return {
        "ok": not failed,
        "failed": failed,
        "skipped": skipped,
        "checks": checks,
        "manifest": manifest,
    }


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, default=str)
