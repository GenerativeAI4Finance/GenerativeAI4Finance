import numpy as np
import pytest
from sklearn import metrics as skm

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


def test_log_loss_clips_hard_zero_and_one():
    y = np.array([1, 0])
    p = np.array([0.0, 1.0])
    # finite, and close to -log(eps) (1 - 1e-15 is not exact in float64)
    assert m.log_loss(y, p) == pytest.approx(-np.log(m.LOG_LOSS_EPS), rel=1e-3)


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


def test_murphy_parts_sum_to_brier(fixture_data):
    y, p = fixture_data
    d = m.murphy_decomposition(y, p)
    total = d["reliability"] - d["resolution"] + d["uncertainty"] + d["within_bin"]
    assert total == pytest.approx(d["brier"])
    assert d["brier"] == pytest.approx(skm.brier_score_loss(y, p))


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
    p = np.array([0.01, 0.02, 0.97, 1.0])
    rows = m.reliability_table(y, p, 10, "width")
    assert len(rows) == 10
    assert [r["n"] for r in rows] == [2, 0, 0, 0, 0, 0, 0, 0, 0, 2]
    assert rows[5]["mean_predicted"] is None and rows[5]["observed_rate"] is None
    # p == 1.0 lands in the last bin, not off the end
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
