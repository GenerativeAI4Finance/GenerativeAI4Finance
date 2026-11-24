import pytest

from gnpa_costs import CostAssumption, cost_sensitive_threshold_report


Y_TRUE = [0, 1, 0, 0, 1, 0, 0, 0, 0, 0]
Y_SCORE = [0.95, 0.80, 0.70, 0.40, 0.55, 0.45, 0.35, 0.29, 0.20, 0.10]
THRESHOLDS = [0.75, 0.50, 0.30]


def assumptions():
    return [
        CostAssumption("balanced", 1, 1, "synthetic units", "Illustrative equal per-case costs."),
        CostAssumption("misses-cost-more", 5, 1, "synthetic units", "Illustrative higher cost for a missed stress case."),
        CostAssumption("alarms-cost-more", 1, 5, "synthetic units", "Illustrative higher cost for a false alarm."),
    ]


def test_costs_recalculate_across_all_thresholds_and_assumptions():
    report = cost_sensitive_threshold_report(Y_TRUE, Y_SCORE, THRESHOLDS, assumptions())
    assert len(report) == len(THRESHOLDS) * 3
    assert report.loc[report["cost_assumption"] == "balanced", "total_cost"].tolist() == [2.0, 2.0, 5.0]
    assert report.loc[report["cost_assumption"] == "misses-cost-more", "total_cost"].tolist() == [6.0, 2.0, 5.0]
    assert report.loc[report["cost_assumption"] == "alarms-cost-more", "total_cost"].tolist() == [6.0, 10.0, 25.0]
    assert report.loc[report["cost_assumption"] == "balanced", "cost_per_observation"].tolist() == [0.2, 0.2, 0.5]


def test_report_exposes_cost_assumptions_and_confusion_counts():
    report = cost_sensitive_threshold_report(Y_TRUE, Y_SCORE, [0.5], [assumptions()[1]])
    row = report.iloc[0]
    assert row["cost_assumption"] == "misses-cost-more"
    assert row["missed_stress_case_cost"] == 5
    assert row["false_alarm_cost"] == 1
    assert row["cost_unit"] == "synthetic units"
    assert row["cost_rationale"] == "Illustrative higher cost for a missed stress case."
    assert (row["tn"], row["fp"], row["fn"], row["tp"]) == (6, 2, 0, 2)
    assert row["recall"] == 1
    assert row["false_positive_rate"] == pytest.approx(0.25)


def test_positive_class_and_score_at_threshold_convention_are_explicit():
    report = cost_sensitive_threshold_report(
        ["ok", "stress", "ok"],
        [0.5, 0.5, 0.1],
        [0.5],
        [CostAssumption("demo", 3, 2, "units", "Test scenario.")],
        pos_label="stress",
    )
    row = report.iloc[0]
    assert row["positive_label"] == "stress"
    assert row["negative_label"] == "ok"
    assert (row["tp"], row["fp"], row["fn"], row["tn"]) == (1, 1, 0, 1)


@pytest.mark.parametrize(
    "y_true, y_score, thresholds, scenarios, message",
    [
        ([0, 1], [0.2], [0.5], assumptions()[:1], "same length"),
        ([0, 1], [0.2, 0.8], [], assumptions()[:1], "at least one value"),
        ([0, 1], [0.2, 0.8], [1.2], assumptions()[:1], "threshold"),
        ([0, 1], [0.2, 0.8], [0.5], [], "at least one cost scenario"),
        ([0, 1], [0.2, 0.8], [0.5], [CostAssumption("bad", -1, 1, "u", "test")], "non-negative"),
        ([0, 1], [0.2, 0.8], [0.5], [CostAssumption("zero", 0, 0, "u", "test")], "greater than zero"),
    ],
)
def test_invalid_inputs_are_rejected(y_true, y_score, thresholds, scenarios, message):
    with pytest.raises((ValueError, TypeError), match=message):
        cost_sensitive_threshold_report(y_true, y_score, thresholds, scenarios)
