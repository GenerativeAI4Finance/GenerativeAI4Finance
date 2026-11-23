# Sample credit-risk benchmark report

**Dataset:** fictional unit-test fixture (10 observations)  
**Positive class:** `1` = event occurs  
**Score convention:** predicted positive when score is greater than or equal to the threshold  
**Metrics:** scikit-learn; PR-AUC is average precision

## Fixture

```text
y_true = [0, 1, 0, 0, 1, 0, 0, 0, 0, 0]
y_score = [0.95, 0.80, 0.70, 0.40, 0.55, 0.45, 0.35, 0.29, 0.20, 0.10]
```

There are 2 positive cases and 8 negative cases. At threshold `0.50`:

| Metric | Result |
|---|---:|
| Accuracy | 0.8000 |
| Precision | 0.5000 |
| Recall | 1.0000 |
| F1 | 0.6667 |
| PR-AUC (average precision) | 0.5000 |
| False-positive rate | 0.2500 |
| Confusion matrix `[[TN, FP], [FN, TP]]` | `[[6, 2], [0, 2]]` |

## Threshold analysis

| Threshold | Precision | Recall | F1 | False positives | False-positive rate | Confusion matrix `[[TN, FP], [FN, TP]]` |
|---:|---:|---:|---:|---:|---:|---|
| 0.75 | 0.5000 | 0.5000 | 0.5000 | 1 | 0.1250 | `[[7, 1], [1, 1]]` |
| 0.50 | 0.5000 | 1.0000 | 0.6667 | 2 | 0.2500 | `[[6, 2], [0, 2]]` |
| 0.30 | 0.2857 | 1.0000 | 0.4444 | 5 | 0.6250 | `[[3, 5], [0, 2]]` |

The threshold changes the number of missed positive cases and false alerts. The metric module reports this trade-off; it does not choose a threshold.

## Accuracy caveat

An all-negative classifier on this fixture also has 80% accuracy, but zero recall because it finds neither positive case. At threshold `0.50`, accuracy remains 80% while both positive cases are found, at the cost of two false positives. This small fixture illustrates why accuracy alone is inadequate for rare-event evaluation. It is not a performance claim about a trained model.
