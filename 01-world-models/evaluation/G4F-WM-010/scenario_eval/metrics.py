"""Scoring and calibration metrics for binary and multi-class probability forecasts.

Everything here works on plain numpy arrays so it can be checked against
scikit-learn in the tests without depending on it at runtime.
"""

import numpy as np

LOG_LOSS_EPS = 1e-15


def check_binary(y, p):
    y = np.asarray(y)
    p = np.asarray(p, dtype=float)
    if y.shape != p.shape or y.ndim != 1:
        raise ValueError("outcomes and probabilities must be 1-d arrays of equal length")
    if len(y) == 0:
        raise ValueError("no rows to evaluate")
    if not np.all(np.isfinite(p)):
        raise ValueError("probabilities contain NaN or inf")
    if p.min() < 0 or p.max() > 1:
        raise ValueError("probabilities must be in [0, 1]")
    if not np.isin(y, (0, 1)).all():
        raise ValueError("binary outcomes must be 0 or 1")
    return y.astype(int), p


def brier(y, p):
    y, p = check_binary(y, p)
    return float(np.mean((p - y) ** 2))


def log_loss(y, p, eps=LOG_LOSS_EPS):
    y, p = check_binary(y, p)
    p = np.clip(p, eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _average_ranks(x):
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ranks = np.empty(len(x))
    # start index of each run of tied values
    starts = np.flatnonzero(np.r_[True, xs[1:] != xs[:-1]])
    ends = np.r_[starts[1:], len(xs)]
    for s, e in zip(starts, ends):
        ranks[order[s:e]] = (s + e + 1) / 2  # mean of 1-based ranks s+1..e
    return ranks


def roc_auc(y, p):
    """Mann-Whitney form of ROC AUC. Returns None if only one class is present."""
    y, p = check_binary(y, p)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = _average_ranks(p)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def average_precision(y, p):
    """Area under the precision-recall curve, step-wise (same definition as sklearn).

    Returns None if only one class is present, to match the AUC behaviour.
    """
    y, p = check_binary(y, p)
    n_pos = int(y.sum())
    if n_pos == 0 or n_pos == len(y):
        return None
    order = np.argsort(-p, kind="mergesort")
    ps, ys = p[order], y[order]
    # one point per distinct threshold, taken at the last row of each tie group
    last = np.r_[np.flatnonzero(ps[1:] != ps[:-1]), len(ps) - 1]
    tp = np.cumsum(ys)[last]
    precision = tp / (last + 1)
    recall = tp / n_pos
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


def bin_edges(p, n_bins, strategy):
    if strategy == "width":
        return np.linspace(0.0, 1.0, n_bins + 1)
    if strategy == "mass":
        edges = np.quantile(p, np.linspace(0.0, 1.0, n_bins + 1))
        edges[0], edges[-1] = 0.0, 1.0
        return edges
    raise ValueError(f"unknown binning strategy: {strategy}")


def assign_bins(p, edges):
    # bins are [lo, hi) except the last one which also takes p == 1.0
    return np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)


def reliability_table(y, p, n_bins=10, strategy="width"):
    """Per-bin counts, mean forecast and observed event rate.

    Empty bins are kept in the table with n=0 and null rates so the reader
    can see where the forecasts never landed. With equal-mass bins, heavy ties
    can produce duplicate edges and therefore empty bins as well.
    """
    y, p = check_binary(y, p)
    edges = bin_edges(p, n_bins, strategy)
    idx = assign_bins(p, edges)
    rows = []
    for k in range(len(edges) - 1):
        mask = idx == k
        n = int(mask.sum())
        rows.append(
            {
                "bin": k,
                "lower": float(edges[k]),
                "upper": float(edges[k + 1]),
                "n": n,
                "mean_predicted": float(p[mask].mean()) if n else None,
                "observed_rate": float(y[mask].mean()) if n else None,
            }
        )
    return rows


def ece(y, p, n_bins=10, strategy="width"):
    """Expected calibration error: sum over bins of n_k/N * |observed_k - predicted_k|."""
    rows = reliability_table(y, p, n_bins, strategy)
    n = sum(r["n"] for r in rows)
    return float(
        sum(r["n"] / n * abs(r["observed_rate"] - r["mean_predicted"]) for r in rows if r["n"])
    )


def murphy_decomposition(y, p, n_bins=10):
    """Brier = reliability - resolution + uncertainty + within_bin.

    The classic Murphy (1973) identity is exact only when every forecast in a
    bin has the same value. With binned continuous forecasts there is an extra
    term (within-bin variance minus within-bin covariance, see Stephenson et
    al. 2008). We report it as `within_bin` so the parts always add up.
    """
    y, p = check_binary(y, p)
    rows = reliability_table(y, p, n_bins, "width")
    n = len(y)
    base_rate = y.mean()
    rel = sum(r["n"] / n * (r["mean_predicted"] - r["observed_rate"]) ** 2 for r in rows if r["n"])
    res = sum(r["n"] / n * (r["observed_rate"] - base_rate) ** 2 for r in rows if r["n"])
    unc = base_rate * (1 - base_rate)
    bs = float(np.mean((p - y) ** 2))
    return {
        "brier": bs,
        "reliability": float(rel),
        "resolution": float(res),
        "uncertainty": float(unc),
        "within_bin": float(bs - (rel - res + unc)),
    }


def check_multiclass(labels, probs, classes):
    labels = np.asarray(labels)
    probs = np.asarray(probs, dtype=float)
    if probs.ndim != 2 or probs.shape != (len(labels), len(classes)):
        raise ValueError("probability matrix must have shape (n_rows, n_classes)")
    if not np.all(np.isfinite(probs)):
        raise ValueError("state probabilities contain NaN or inf")
    if probs.min() < 0 or probs.max() > 1:
        raise ValueError("state probabilities must be in [0, 1]")
    if not np.allclose(probs.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("state probabilities must sum to 1 on every row")
    unknown = set(labels.tolist()) - set(classes)
    if unknown:
        raise ValueError(f"observed states not in the predicted classes: {sorted(unknown)}")
    onehot = (labels[:, None] == np.asarray(classes)[None, :]).astype(float)
    return onehot, probs


def multiclass_brier(labels, probs, classes):
    """Sum over classes of squared error, averaged over rows. Range [0, 2]."""
    onehot, probs = check_multiclass(labels, probs, classes)
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def multiclass_log_loss(labels, probs, classes, eps=LOG_LOSS_EPS):
    onehot, probs = check_multiclass(labels, probs, classes)
    p_true = np.clip(np.sum(probs * onehot, axis=1), eps, 1.0)
    return float(-np.mean(np.log(p_true)))


def percentile_ci(values, level=0.95):
    values = np.asarray([v for v in values if v is not None], dtype=float)
    if len(values) == 0:
        return None
    alpha = (1 - level) / 2
    lo, hi = np.quantile(values, [alpha, 1 - alpha])
    return [float(lo), float(hi)]


def bootstrap(y, p, metric_fns, n_boot=500, seed=0, level=0.95):
    """Percentile bootstrap over rows. Resamples where a metric is undefined
    (e.g. AUC on a single-class draw) are dropped and counted."""
    y, p = check_binary(y, p)
    rng = np.random.default_rng(seed)
    draws = {name: [] for name in metric_fns}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        for name, fn in metric_fns.items():
            draws[name].append(fn(y[i], p[i]))
    out = {}
    for name, vals in draws.items():
        out[name] = {
            "ci": percentile_ci(vals, level),
            "undefined_draws": sum(v is None for v in vals),
        }
    return out
