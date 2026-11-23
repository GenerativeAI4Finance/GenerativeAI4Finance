# G4F-GNPA-003: Credit-risk benchmark metrics

## Purpose and compatibility

A small binary-classification metrics package for evaluating early-warning labels such as `new_npa_within_90d` from [G4F-GNPA-002](../G4F-GNPA-002/README.md). Inputs are observed binary labels and model scores; this module does not train a model, generate labels, or select an operational decision threshold.

## Definitions

- The **positive class** is passed explicitly as `pos_label` (default `1`). The other of the two observed labels is the negative class.
- A record is predicted positive when `score >= threshold`; both score and threshold must be in `[0, 1]`.
- Precision, recall, F1, accuracy, and confusion-matrix counts are calculated at the requested threshold. The confusion matrix order is `[negative_label, positive_label]`, so its layout is `[[TN, FP], [FN, TP]]`.
- PR-AUC is reported as scikit-learn's `average_precision_score`, labeled `pr_auc_average_precision`. Average precision is a step-wise, non-interpolated summary of the precision-recall curve; it is not trapezoidal area under a plotted curve.
- `false_positive_rate = FP / (FP + TN)`. Threshold analysis also reports the absolute number of false positives and recall to make the operational trade-off visible.
- Inputs with missing/non-finite/out-of-range scores, mismatched lengths, a missing positive class, or other than two observed classes are rejected. If a threshold predicts no positives, precision, recall, and F1 use zero for undefined values.

## Why accuracy alone misleads

With rare events, a model that predicts every case as negative can achieve high accuracy while finding no positive events. In the sample fixture below, only 2 of 10 cases are positive. An all-negative prediction has 80% accuracy and zero recall. At threshold 0.50, accuracy is still 80%, while recall is 100%; the threshold also produces two false positives. Accuracy hides both the missed-event behavior of the trivial model and the false-positive cost of a thresholded model. Report class counts, precision, recall, PR-AUC, and the confusion matrix alongside accuracy.

## Usage

From this folder:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

Example:

```python
from gnpa_metrics import analyze_thresholds, evaluate_binary_classifier

# y_true can be new_npa_within_90d from GNPA-002 after dropping null labels.
# y_score must contain model scores for those same rows in the same order.
result = evaluate_binary_classifier(y_true, y_score, threshold=0.50, pos_label=1)
thresholds = analyze_thresholds(y_true, y_score, [0.75, 0.50, 0.30], pos_label=1)
```

Do not include censored/null labels in metric inputs. Keep the same filtered rows and ordering for labels and scores. Select thresholds using a declared validation procedure; do not tune on a final test set.

## Files

- `gnpa_metrics/credit_metrics.py`: metric and threshold-analysis functions.
- `tests/test_credit_metrics.py`: trusted-library comparisons and input/threshold cases.
- `reports/sample_report.md`: worked imbalanced fixture and threshold analysis.
- `requirements.txt`: evaluation dependencies.

## Sample report

See [reports/sample_report.md](reports/sample_report.md). It is a tiny illustrative fixture, not an empirical performance claim or evidence of production readiness.
