import numpy as np
import pytest
from sklearn import metrics as skm
from sklearn.calibration import calibration_curve

from scenario_eval import metrics as m


@pytest.fixture
def fixture_data():
    rng = np.random.default_rng(42)
    p = rng.uniform(0, 1, 500)
    y = (rng.uniform(0, 1, 500) < p).astype(int)
    return y, p


@pytest.fixture
def tied_data():
    # coarse probabilities so there are many ties
    rng = np.random.default_rng(3)
    p = rng.integers(0, 11, 300) / 10
    y = (rng.uniform(0, 1, 300) < p).astype(int)
    return y, p


def test_brier_and_log_loss_match_sklearn(fixture_data):
    y, p = fixture_data
    assert m.brier(y, p) == pytest.approx(skm.brier_score_loss(y, p))
    assert m.log_loss(y, p) == pytest.approx(skm.log_loss(y, p))


@pytest.mark.parametrize("data", ["fixture_data", "tied_data"])
def test_discrimination_matches_sklearn(data, request):
    y, p = request.getfixturevalue(data)
    assert m.roc_auc(y, p) == pytest.approx(skm.roc_auc_score(y, p))
    assert m.average_precision(y, p) == pytest.approx(skm.average_precision_score(y, p))


def test_log_loss_clip_matches_hand_values():
    # an event forecast at 0 is clipped to 1e-15: -log(1e-15) = 15 ln 10
    assert m.log_loss([1], [0.0]) == pytest.approx(34.538776394910684, rel=1e-12)
    # a non-event forecast at 1 is clipped to 1 - 1e-15, and 1 - (1 - 1e-15)
    # is 9.992007221626409e-16 in float64, so the loss is a little larger
    assert m.log_loss([0], [1.0]) == pytest.approx(34.53957599234088, rel=1e-12)


def test_log_loss_differs_from_sklearn_only_by_the_clip():
    y = np.array([1, 0, 1])
    p = np.array([0.0, 1.0, 0.5])
    # current scikit-learn clips at machine epsilon instead of 1e-15
    assert m.log_loss(y, p, eps=np.finfo(float).eps) == pytest.approx(skm.log_loss(y, p))
    assert m.log_loss(y, p) < skm.log_loss(y, p)


def test_multiclass_matches_sklearn():
    rng = np.random.default_rng(1)
    # sklearn expects the columns in sorted label order
    classes = ["current", "default", "delinquent"]
    probs = rng.dirichlet([5, 2, 1], 400)
    labels = np.array([rng.choice(classes, p=row) for row in probs])
    assert m.multiclass_log_loss(labels, probs, classes) == pytest.approx(
        skm.log_loss(labels, probs, labels=classes)
    )
    assert m.multiclass_brier(labels, probs, classes) == pytest.approx(
        skm.brier_score_loss(labels, probs, labels=classes, scale_by_half=False)
    )


def test_multiclass_rejects_rows_not_summing_to_one():
    with pytest.raises(ValueError, match="sum to 1"):
        m.multiclass_brier(["a"], [[0.5, 0.4]], ["a", "b"])


@pytest.mark.parametrize("metric", [m.multiclass_brier, m.multiclass_log_loss])
def test_multiclass_uses_absolute_probability_sum_tolerance(metric):
    with pytest.raises(ValueError, match="sum to 1"):
        metric(["a"], [[0.500005, 0.500005]], ["a", "b"])
    assert np.isfinite(metric(["a"], [[0.5000002, 0.5000002]], ["a", "b"]))


@pytest.mark.parametrize("imaginary", [0.0, 0.2])
def test_metrics_reject_complex_probabilities(imaginary):
    with pytest.raises(ValueError, match="real values"):
        m.brier([0, 1], np.array([0.2 + imaginary * 1j, 0.8]))
    with pytest.raises(ValueError, match="real values"):
        m.multiclass_brier(["a"], [[0.5 + imaginary * 1j, 0.5 - imaginary * 1j]], ["a", "b"])


def test_binary_metrics_reject_complex_outcomes():
    with pytest.raises(ValueError, match="real values"):
        m.brier(np.array([0.0j, 1.0 + 0.0j]), [0.2, 0.8])


def test_multiclass_rejects_unknown_state():
    with pytest.raises(ValueError, match="not in the predicted classes"):
        m.multiclass_brier(["c"], [[0.5, 0.5]], ["a", "b"])


@pytest.mark.parametrize("strategy", ["width", "mass"])
def test_calibrated_forecasts_have_small_ece(strategy):
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 200_000)
    y = (rng.uniform(0, 1, len(p)) < p).astype(int)
    assert m.ece(y, p, 10, strategy) < 0.01


@pytest.mark.parametrize("strategy", ["width", "mass"])
def test_known_miscalibration_is_detected(strategy):
    rng = np.random.default_rng(0)
    p_true = rng.uniform(0, 1, 200_000)
    y = (rng.uniform(0, 1, len(p_true)) < p_true).astype(int)
    # forecaster reports half the true probability, so the gap is mean(p_true) / 2
    assert m.ece(y, p_true / 2, 10, strategy) == pytest.approx(0.25, abs=0.01)


def test_ece_matches_hand_computation():
    y = np.array([0, 1, 1, 1])
    p = np.array([0.05, 0.05, 0.95, 0.95])
    # bin 0: pred 0.05, obs 0.5 ; bin 9: pred 0.95, obs 1.0
    assert m.ece(y, p) == pytest.approx(0.5 * 0.45 + 0.5 * 0.05)
    # MCE is the larger of the two gaps
    assert m.mce(y, p) == pytest.approx(0.45)


@pytest.mark.parametrize("strategy", ["width", "mass"])
def test_mce_is_at_least_ece(fixture_data, strategy):
    y, p = fixture_data
    assert m.mce(y, p, 10, strategy) >= m.ece(y, p, 10, strategy)


def test_one_bin_ece_is_calibration_in_the_large(fixture_data):
    y, p = fixture_data
    assert m.ece(y, p, 1) == pytest.approx(abs(p.mean() - y.mean()))


def test_equal_width_edges_are_the_decimal_values():
    edges = m.bin_edges(None, 10, "width")
    assert edges.tolist() == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


@pytest.mark.parametrize("container", [list, tuple])
def test_equal_mass_edges_accept_array_like_probabilities(container):
    p = container([0.1, 0.1, 0.3, 0.7, 0.9])
    expected = np.quantile(p, np.linspace(0.0, 1.0, 5))
    expected[0], expected[-1] = 0.0, 1.0
    assert np.array_equal(m.bin_edges(p, 4, "mass"), expected)


@pytest.mark.parametrize("n_bins", [1, 2, 3, 4, 5, 7, 10, 20, 49, 100])
def test_grid_values_land_in_the_bin_they_open(n_bins):
    # k / n_bins opens bin k, and 1.0 stays in the last bin
    p = np.arange(n_bins + 1) / n_bins
    idx = m.assign_bins(p, m.bin_edges(p, n_bins, "width"))
    assert idx.tolist() == list(range(n_bins)) + [n_bins - 1]


def test_decimal_forecasts_follow_the_lower_closed_rule():
    # 0.0, 0.1, ..., 0.9, 1.0 as they would be read from a CSV
    p = np.array([float(f"0.{k}") for k in range(10)] + [1.0])
    rows = m.reliability_table(np.zeros(len(p), dtype=int), p, 10, "width")
    assert [r["n"] for r in rows] == [1] * 9 + [2]
    for r in rows[:9]:
        assert r["mean_predicted"] == r["lower"]


def test_forecasts_on_bin_edges_are_not_merged():
    # 0.2 comes true 30% of the time and 0.3 comes true 20% of the time, so
    # both miss by 0.1. If they shared a bin the gaps would cancel to ECE 0.
    p = np.r_[np.full(5000, 0.2), np.full(5000, 0.3)]
    y = np.r_[np.ones(1500), np.zeros(3500), np.ones(1000), np.zeros(4000)].astype(int)
    rows = [r for r in m.reliability_table(y, p) if r["n"]]
    assert [(r["lower"], r["n"]) for r in rows] == [(0.2, 5000), (0.3, 5000)]
    assert m.ece(y, p) == pytest.approx(0.1)
    d = m.murphy_decomposition(y, p)
    assert d["reliability"] == pytest.approx(0.01)
    assert d["within_bin"] == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("strategy, sk_strategy", [("width", "uniform"), ("mass", "quantile")])
def test_reliability_table_matches_sklearn_on_continuous_data(strategy, sk_strategy):
    # sklearn's calibration_curve uses (lo, hi] bins and np.linspace edges, so
    # it only differs from ours for a forecast exactly on an edge; continuous
    # data has none (with 2000 rows no quantile edge falls on a data point)
    rng = np.random.default_rng(8)
    p = rng.beta(1, 6, 2000)
    y = (rng.uniform(size=len(p)) < p).astype(int)
    prob_true, prob_pred = calibration_curve(y, p, n_bins=10, strategy=sk_strategy)
    rows = [r for r in m.reliability_table(y, p, 10, strategy) if r["n"]]
    assert [r["observed_rate"] for r in rows] == pytest.approx(prob_true, abs=1e-14)
    assert [r["mean_predicted"] for r in rows] == pytest.approx(prob_pred, abs=1e-14)


def test_ece_matches_sklearn_calibration_curve_on_continuous_data():
    rng = np.random.default_rng(9)
    p = rng.beta(2, 5, 3000)
    y = (rng.uniform(size=len(p)) < np.clip(p * 1.3, 0, 1)).astype(int)
    prob_true, prob_pred = calibration_curve(y, p, n_bins=10, strategy="uniform")
    counts, _ = np.histogram(p, bins=10, range=(0, 1))
    counts = counts[counts > 0]
    expected = np.sum(counts / len(p) * np.abs(prob_true - prob_pred))
    assert m.ece(y, p, 10, "width") == pytest.approx(expected, abs=1e-14)


@pytest.mark.parametrize("bad", [0, -1, m.MAX_BINS + 1])
def test_n_bins_out_of_range_is_rejected(bad):
    y, p = np.array([0, 1]), np.array([0.2, 0.7])
    fns = (m.reliability_table, m.ece, m.mce, m.murphy_decomposition, m.reliability_debiased)
    for fn in fns:
        with pytest.raises(ValueError, match="n_bins must be between 1 and"):
            fn(y, p, bad)


@pytest.mark.parametrize("bad", [2.5, "10", True])
def test_n_bins_must_be_an_integer(bad):
    with pytest.raises(TypeError, match="n_bins must be an integer"):
        m.ece([0, 1], [0.2, 0.7], bad)


def test_murphy_terms_match_hand_computation():
    # equal-width bins: {0.05}, {0.12, 0.15, 0.18}, {0.62, 0.68}
    p = np.array([0.05, 0.12, 0.15, 0.18, 0.62, 0.68])
    y = np.array([0, 1, 0, 0, 1, 0])
    base = 2 / 6
    rel = (1 * (0.05 - 0) ** 2 + 3 * (0.15 - 1 / 3) ** 2 + 2 * (0.65 - 0.5) ** 2) / 6
    res = (1 * (0 - base) ** 2 + 3 * (1 / 3 - base) ** 2 + 2 * (0.5 - base) ** 2) / 6
    unc = base * (1 - base)
    # within-bin variance of the forecasts and their covariance with the outcomes
    wbv = (0.03**2 + 0 + 0.03**2 + 0.03**2 + 0.03**2) / 6
    wbc = (-0.03 * (2 / 3) + 0.03 * (-1 / 3) + -0.03 * 0.5 + 0.03 * -0.5) / 6
    d = m.murphy_decomposition(y, p)
    assert d["reliability"] == pytest.approx(rel)
    assert d["resolution"] == pytest.approx(res)
    assert d["uncertainty"] == pytest.approx(unc)
    assert d["within_bin"] == pytest.approx(wbv - 2 * wbc)
    # the hand terms, none of them a remainder, add up to the Brier score
    assert rel - res + unc + wbv - 2 * wbc == pytest.approx(np.mean((p - y) ** 2))
    assert d["brier"] == pytest.approx(skm.brier_score_loss(y, p))


def test_murphy_within_bin_matches_direct_formula(fixture_data):
    y, p = fixture_data
    idx = np.minimum((p * 10).astype(int), 9)  # continuous data, no forecast on an edge
    wbv = wbc = 0.0
    for k in np.unique(idx):
        pk, yk = p[idx == k], y[idx == k]
        wbv += np.sum((pk - pk.mean()) ** 2)
        wbc += np.sum((pk - pk.mean()) * (yk - yk.mean()))
    d = m.murphy_decomposition(y, p)
    assert d["within_bin"] == pytest.approx((wbv - 2 * wbc) / len(p))


def test_murphy_is_exact_for_one_value_per_bin():
    rng = np.random.default_rng(5)
    p = rng.choice([0.05, 0.25, 0.55, 0.85], 2000)
    y = (rng.uniform(0, 1, len(p)) < p).astype(int)
    d = m.murphy_decomposition(y, p)
    assert d["within_bin"] == pytest.approx(0, abs=1e-12)
    assert d["uncertainty"] == pytest.approx(y.mean() * (1 - y.mean()))


def test_climatology_forecast_has_no_reliability_or_resolution():
    y = np.array([0, 0, 0, 1] * 25)
    p = np.full(len(y), 0.25)
    d = m.murphy_decomposition(y, p)
    assert d["reliability"] == pytest.approx(0)
    assert d["resolution"] == pytest.approx(0)
    assert d["brier"] == pytest.approx(d["uncertainty"]) == pytest.approx(0.1875)


def test_reliability_debiased_matches_hand_computation():
    # one 4-row bin and one 1-row bin; the single row cannot be debiased
    p = np.array([0.25, 0.25, 0.25, 0.25, 0.85])
    y = np.array([1, 1, 0, 0, 0])
    # 4-row bin: gap (0.25 - 0.5)^2 = 0.0625, noise 0.5 * 0.5 / 3
    expected = 4 / 5 * (0.0625 - 0.25 / 3) + 1 / 5 * 0.85**2
    assert m.reliability_debiased(y, p) == pytest.approx(expected)
    assert m.murphy_decomposition(y, p)["reliability"] == pytest.approx(
        4 / 5 * 0.0625 + 1 / 5 * 0.85**2
    )


def test_reliability_debiased_removes_the_noise_bias():
    # one forecast value per bin, each 0.04 below the true probability
    rng = np.random.default_rng(11)
    p = np.repeat([0.05, 0.25, 0.55], [300, 150, 50])
    q = p + 0.04
    true_rel = np.mean((p - q) ** 2)
    plug_in, debiased = [], []
    for _ in range(1000):
        y = (rng.uniform(size=len(p)) < q).astype(int)
        plug_in.append(m.murphy_decomposition(y, p)["reliability"])
        debiased.append(m.reliability_debiased(y, p))
    # expected noise in the plug-in value is sum_k n_k/N q_k (1 - q_k) / n_k, about 0.001
    plug_in_bias = np.mean(plug_in) - true_rel
    debiased_bias = np.mean(debiased) - true_rel
    # the Monte Carlo standard error of each mean is about 5e-5, so allow 4 of them
    assert plug_in_bias == pytest.approx(0.00106, abs=2e-4)
    assert abs(debiased_bias) < 2e-4
    assert abs(debiased_bias) < 0.3 * plug_in_bias


def test_single_class_gives_none_not_zero():
    y = np.zeros(10, dtype=int)
    p = np.linspace(0, 0.5, 10)
    assert m.roc_auc(y, p) is None
    assert m.average_precision(y, p) is None
    assert m.roc_auc(1 - y, p) is None


@pytest.mark.parametrize("bad", [[0.2, 1.2], [-0.1, 0.5], [np.nan, 0.5], [np.inf, 0.5]])
def test_rejects_invalid_probabilities(bad):
    with pytest.raises(ValueError):
        m.brier([0, 1], bad)


def test_rejects_non_binary_outcomes():
    with pytest.raises(ValueError, match="0 or 1"):
        m.brier([0, 2], [0.1, 0.2])


def test_empty_bins_are_kept_with_null_rates():
    y = np.array([0, 1, 0, 1])
    p = np.array([0.0, 0.02, 0.97, 1.0])
    rows = m.reliability_table(y, p, 10, "width")
    assert len(rows) == 10
    assert [r["n"] for r in rows] == [2, 0, 0, 0, 0, 0, 0, 0, 0, 2]
    assert rows[5]["mean_predicted"] is None and rows[5]["observed_rate"] is None
    # p == 0.0 lands in the first bin and p == 1.0 in the last, not off the end
    assert rows[0]["mean_predicted"] == pytest.approx(0.01)
    assert rows[9]["mean_predicted"] == pytest.approx(0.985)


def test_equal_mass_bins_have_similar_counts(fixture_data):
    y, p = fixture_data
    counts = [r["n"] for r in m.reliability_table(y, p, 10, "mass")]
    assert sum(counts) == len(p)
    assert max(counts) - min(counts) <= 1


def test_bootstrap_is_deterministic_and_counts_undefined_draws():
    y = np.array([0] * 48 + [1, 1])
    p = np.linspace(0.01, 0.6, 50)
    fns = {"brier": m.brier, "roc_auc": m.roc_auc}
    a = m.bootstrap(y, p, fns, n_boot=200, seed=11)
    b = m.bootstrap(y, p, fns, n_boot=200, seed=11)
    assert a == b
    assert a["brier"]["undefined_draws"] == 0
    # with only two positives, some resamples contain none of them
    assert a["roc_auc"]["undefined_draws"] > 0
    lo, hi = a["brier"]["ci"]
    assert lo <= m.brier(y, p) <= hi


def test_bootstrap_does_not_report_degenerate_intervals():
    # one row: every resample is the same row, so the interval would be [x, x]
    out = m.bootstrap([1], [0.3], {"brier": m.brier, "roc_auc": m.roc_auc}, n_boot=20)
    assert out["brier"]["ci"] is None
    assert out["brier"]["ci_null_reason"] == m.ZERO_WIDTH
    assert out["roc_auc"]["ci"] is None
    assert out["roc_auc"]["ci_null_reason"] == m.UNDEFINED


@pytest.mark.parametrize("bad", [0, -5])
def test_bootstrap_needs_at_least_one_resample(bad):
    with pytest.raises(ValueError, match="n_boot must be at least 1"):
        m.bootstrap([0, 1], [0.2, 0.7], {"brier": m.brier}, n_boot=bad)
