import pytest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from gnpa_metrics import analyze_thresholds, evaluate_binary_classifier


Y_TRUE = [0, 1, 0, 0, 1, 0, 0, 0, 0, 0]
Y_SCORE = [0.95, 0.80, 0.70, 0.40, 0.55, 0.45, 0.35, 0.29, 0.20, 0.10]


def test_metrics_match_scikit_learn_on_known_imbalanced_fixture():
    result = evaluate_binary_classifier(Y_TRUE, Y_SCORE, threshold=0.5, pos_label=1)
    pred = [int(score >= 0.5) for score in Y_SCORE]
    assert result["positive_label"] == 1
    assert result["negative_label"] == 0
    assert result["accuracy"] == pytest.approx(0.8)
    assert result["precision"] == pytest.approx(precision_score(Y_TRUE, pred, zero_division=0))
    assert result["recall"] == pytest.approx(recall_score(Y_TRUE, pred, zero_division=0))
    assert result["f1"] == pytest.approx(f1_score(Y_TRUE, pred, zero_division=0))
    assert result["pr_auc_average_precision"] == pytest.approx(average_precision_score(Y_TRUE, Y_SCORE, pos_label=1))
    expected = confusion_matrix(Y_TRUE, pred, labels=[0, 1]).tolist()
    assert result["confusion_matrix"]["matrix"] == expected == [[6, 2], [0, 2]]
    assert result["confusion_matrix"]["fp"] == 2
    assert result["confusion_matrix"]["fn"] == 0


def test_threshold_report_exposes_recall_and_false_positive_tradeoff():
    report = analyze_thresholds(Y_TRUE, Y_SCORE, [0.75, 0.5, 0.3], pos_label=1)
    assert [row["threshold"] for row in report] == [0.75, 0.5, 0.3]
    assert [row["recall"] for row in report] == pytest.approx([0.5, 1.0, 1.0])
    assert [row["false_positives"] for row in report] == [1, 2, 5]
    assert report[1]["false_positive_rate"] == pytest.approx(2 / 8)


def test_string_positive_class_is_supported():
    result = evaluate_binary_classifier(["no", "yes", "no"], [0.1, 0.8, 0.7], pos_label="yes")
    assert result["positive_label"] == "yes"
    assert result["negative_label"] == "no"
    assert result["confusion_matrix"]["tp"] == 1
    assert result["confusion_matrix"]["fp"] == 1


def test_no_predicted_positives_has_zero_precision_and_recall():
    result = evaluate_binary_classifier([0, 1], [0.1, 0.2], threshold=0.5)
    assert result["precision"] == 0
    assert result["recall"] == 0
    assert result["f1"] == 0


@pytest.mark.parametrize(
    "args, message",
    [
        (([0, 1], [0.2], 0.5, 1), "same length"),
        (([0, 1], [0.2, float("nan")], 0.5, 1), "finite"),
        (([0, 1], [0.2, 1.1], 0.5, 1), "probabilities"),
        (([0, 1], [0.2, 0.8], 1.1, 1), "threshold"),
        (([0, 1, 2], [0.1, 0.8, 0.7], 0.5, 1), "exactly two classes"),
    ],
)
def test_invalid_inputs_are_rejected(args, message):
    y_true, y_score, threshold, pos_label = args
    with pytest.raises(ValueError, match=message):
        evaluate_binary_classifier(y_true, y_score, threshold=threshold, pos_label=pos_label)

