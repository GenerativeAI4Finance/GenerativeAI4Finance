# Worked synthetic cost-sensitive example

**Dataset:** fictional ten-row fixture shared in style with G4F-GNPA-003  
**Positive class:** `1` = stress case  
**Prediction rule:** positive when `score >= threshold`  
**Cost unit:** illustrative synthetic units per case; not an estimate of real-world costs

```text
y_true  = [0, 1, 0, 0, 1, 0, 0, 0, 0, 0]
y_score = [0.95, 0.80, 0.70, 0.40, 0.55, 0.45, 0.35, 0.29, 0.20, 0.10]
```

The threshold confusion counts are:

| Threshold | Recall | False-positive rate | TN | FP | FN | TP |
|---:|---:|---:|---:|---:|---:|---:|
| 0.75 | 0.5000 | 0.1250 | 7 | 1 | 1 | 1 |
| 0.50 | 1.0000 | 0.2500 | 6 | 2 | 0 | 2 |
| 0.30 | 1.0000 | 0.6250 | 3 | 5 | 0 | 2 |

The cost scenarios below are sensitivity examples. Each is explicitly named and described; none is proposed as the right ratio for another portfolio or institution.

| Cost scenario | Missed stress case cost (FN) | False alarm cost (FP) | Threshold 0.75 | Threshold 0.50 | Threshold 0.30 | Lowest cost in this fixture |
|---|---:|---:|---:|---:|---:|---|
| Balanced illustrative | 1 | 1 | 2 | 2 | 5 | 0.75 and 0.50 tie |
| Misses cost more | 5 | 1 | 6 | 2 | 5 | 0.50 |
| False alarms cost more | 1 | 5 | 6 | 10 | 25 | 0.75 |

For example, at threshold 0.75 under “misses cost more,” `total_cost = 1 FN × 5 + 1 FP × 1 = 6` synthetic units. At threshold 0.50, `0 FN × 5 + 2 FP × 1 = 2` synthetic units. The output also reports cost per observation by dividing total cost by 10.

The lowest-cost threshold changes when the assumptions change. This is a property of this tiny fixture, not a general threshold recommendation. Real use requires institution-specific, documented, reviewed cost assumptions and validation on data that was not used to fit the model or set the threshold.
