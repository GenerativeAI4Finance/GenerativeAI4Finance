"""Scoring and calibration metrics for binary and multi-class probability forecasts.

Everything here works on plain numpy arrays so it can be checked against
scikit-learn in the tests without depending on it at runtime.
"""

from collections.abc import Callable, Mapping

import numpy as np
from numpy.typing import ArrayLike

# Forecasts are clipped to [LOG_LOSS_EPS, 1 - LOG_LOSS_EPS] before taking logs,
# so a confident miss costs about 34.5 instead of infinity. Current
# scikit-learn clips at machine epsilon (about 2.2e-16) instead, so the two
# only differ for forecasts within 1e-15 of 0 or 1.
LOG_LOSS_EPS = 1e-15
MAX_BINS = 100

UNDEFINED = "undefined on every resample"
ZERO_WIDTH = "zero width: the lower and upper resample quantiles are equal"

MetricFn = Callable[[np.ndarray, np.ndarray], float | None]


def check_binary(y: ArrayLike, p: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y)
    if np.iscomplexobj(y):
        raise ValueError("binary outcomes must be real values 0 or 1")
    if np.iscomplexobj(np.asarray(p)):
        raise ValueError("probabilities must be real values in [0, 1]")
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


def check_int(name: str, value: int, lo: int, hi: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise TypeError(f"{name} must be an integer, got {value!r}")
    if value < lo or (hi is not None and value > hi):
        bounds = f"between {lo} and {hi}" if hi is not None else f"at least {lo}"
        raise ValueError(f"{name} must be {bounds}, got {value}")
    return int(value)


def check_n_bins(n_bins: int) -> int:
    return check_int("n_bins", n_bins, 1, MAX_BINS)


def brier(y: ArrayLike, p: ArrayLike) -> float:
    y, p = check_binary(y, p)
    return float(np.mean((p - y) ** 2))


def log_loss(y: ArrayLike, p: ArrayLike, eps: float = LOG_LOSS_EPS) -> float:
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


def roc_auc(y: ArrayLike, p: ArrayLike) -> float | None:
    """Mann-Whitney form of ROC AUC. Returns None if only one class is present."""
    y, p = check_binary(y, p)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = _average_ranks(p)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def average_precision(y: ArrayLike, p: ArrayLike) -> float | None:
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


def bin_edges(p: ArrayLike | None, n_bins: int, strategy: str) -> np.ndarray:
    n_bins = check_n_bins(n_bins)
    if strategy == "width":
        # k / n_bins is correctly rounded, so every edge is the same float as
        # the decimal it stands for (0.3, not the 0.30000000000000004 that
        # np.linspace gives) and a forecast of exactly 0.3 lands in [0.3, 0.4).
        return np.arange(n_bins + 1) / n_bins
    if strategy == "mass":
        edges = np.quantile(p, np.linspace(0.0, 1.0, n_bins + 1))
        edges[0], edges[-1] = 0.0, 1.0
        return edges
    raise ValueError(f"unknown binning strategy: {strategy}")


def assign_bins(p: ArrayLike, edges: np.ndarray) -> np.ndarray:
    # bins are [lo, hi) except the last one which also takes p == 1.0
    return np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)


def reliability_table(
    y: ArrayLike, p: ArrayLike, n_bins: int = 10, strategy: str = "width"
) -> list[dict]:
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
    # defensive: every row must land in exactly one bin
    if sum(r["n"] for r in rows) != len(y):
        raise RuntimeError("reliability bin counts do not add up to the number of rows")
    return rows


def ece(y: ArrayLike, p: ArrayLike, n_bins: int = 10, strategy: str = "width") -> float:
    """Expected calibration error: sum over bins of n_k/N * |observed_k - predicted_k|."""
    rows = reliability_table(y, p, n_bins, strategy)
    n = sum(r["n"] for r in rows)
    return float(
        sum(r["n"] / n * abs(r["observed_rate"] - r["mean_predicted"]) for r in rows if r["n"])
    )


def mce(y: ArrayLike, p: ArrayLike, n_bins: int = 10, strategy: str = "width") -> float:
    """Maximum calibration error: the largest |observed_k - predicted_k| over non-empty bins.

    It is usually set by one of the smallest bins, so read it with that bin's count.
    """
    rows = reliability_table(y, p, n_bins, strategy)
    return float(max(abs(r["observed_rate"] - r["mean_predicted"]) for r in rows if r["n"]))


def murphy_decomposition(y: ArrayLike, p: ArrayLike, n_bins: int = 10) -> dict[str, float]:
    """Brier = reliability - resolution + uncertainty + within_bin.

    The classic Murphy (1973) identity is exact only when every forecast in a
    bin has the same value. With binned continuous forecasts there is an extra
    term (within-bin variance minus twice the within-bin covariance, see
    Stephenson et al. 2008). It is reported as `within_bin`, computed as the
    remainder so the parts always add up; the tests check it against the
    direct formula.
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


def reliability_debiased(y: ArrayLike, p: ArrayLike, n_bins: int = 10) -> float:
    """Murphy reliability with the sampling noise of each bin's observed rate taken out.

    The plug-in reliability sum_k n_k/N (predicted_k - observed_k)^2 is the
    squared calibration error, and binomial noise in observed_k pushes it up
    even for a perfectly calibrated forecaster. Subtracting the unbiased
    estimate of that noise, observed_k (1 - observed_k) / (n_k - 1), gives the
    debiased estimator of Kumar, Liang and Ma (2019). It is unbiased when the
    rows in a bin share one true event probability and slightly low otherwise,
    so it can come out a little below 0 when the gap is within noise. A bin
    with a single row has no variance estimate and keeps its plug-in term.
    """
    y, p = check_binary(y, p)
    rows = reliability_table(y, p, n_bins, "width")
    n = len(y)
    total = 0.0
    for r in rows:
        if not r["n"]:
            continue
        term = (r["mean_predicted"] - r["observed_rate"]) ** 2
        if r["n"] > 1:
            term -= r["observed_rate"] * (1 - r["observed_rate"]) / (r["n"] - 1)
        total += r["n"] / n * term
    return float(total)


def check_multiclass(
    labels: ArrayLike, probs: ArrayLike, classes: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(labels)
    if np.iscomplexobj(np.asarray(probs)):
        raise ValueError("state probabilities must be real values in [0, 1]")
    probs = np.asarray(probs, dtype=float)
    if probs.ndim != 2 or probs.shape != (len(labels), len(classes)):
        raise ValueError("probability matrix must have shape (n_rows, n_classes)")
    if not np.all(np.isfinite(probs)):
        raise ValueError("state probabilities contain NaN or inf")
    if probs.min() < 0 or probs.max() > 1:
        raise ValueError("state probabilities must be in [0, 1]")
    if not np.allclose(probs.sum(axis=1), 1.0, atol=1e-6, rtol=0):
        raise ValueError("state probabilities must sum to 1 on every row")
    unknown = set(labels.tolist()) - set(classes)
    if unknown:
        raise ValueError(
            f"observed states not in the predicted classes: {sorted(map(str, unknown))}"
        )
    onehot = (labels[:, None] == np.asarray(classes)[None, :]).astype(float)
    return onehot, probs


def multiclass_brier(labels: ArrayLike, probs: ArrayLike, classes: list[str]) -> float:
    """Sum over classes of squared error, averaged over rows. Range [0, 2]."""
    onehot, probs = check_multiclass(labels, probs, classes)
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def multiclass_log_loss(
    labels: ArrayLike, probs: ArrayLike, classes: list[str], eps: float = LOG_LOSS_EPS
) -> float:
    onehot, probs = check_multiclass(labels, probs, classes)
    p_true = np.clip(np.sum(probs * onehot, axis=1), eps, 1.0)
    return float(-np.mean(np.log(p_true)))


def percentile_ci(values: list[float | None], level: float = 0.95) -> list[float] | None:
    values = np.asarray([v for v in values if v is not None], dtype=float)
    if len(values) == 0:
        return None
    alpha = (1 - level) / 2
    lo, hi = np.quantile(values, [alpha, 1 - alpha])
    return [float(lo), float(hi)]


def bootstrap(
    y: ArrayLike,
    p: ArrayLike,
    metric_fns: Mapping[str, MetricFn],
    n_boot: int = 500,
    seed: int = 0,
    level: float = 0.95,
) -> dict[str, dict]:
    """Percentile bootstrap over rows. Resamples where a metric is undefined
    (e.g. AUC on a single-class draw) are dropped and counted.

    An interval of zero width (tiny or constant samples) carries no
    information, so it is returned as None with a reason rather than as [x, x].
    """
    n_boot = check_int("n_boot", n_boot, 1)
    y, p = check_binary(y, p)
    rng = np.random.default_rng(seed)
    draws = {name: [] for name in metric_fns}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        for name, fn in metric_fns.items():
            draws[name].append(fn(y[i], p[i]))
    out = {}
    for name, vals in draws.items():
        ci = percentile_ci(vals, level)
        reason = None
        if ci is None:
            reason = UNDEFINED
        elif ci[0] == ci[1]:
            ci, reason = None, ZERO_WIDTH
        out[name] = {
            "ci": ci,
            "ci_null_reason": reason,
            "undefined_draws": sum(v is None for v in vals),
        }
    return out
