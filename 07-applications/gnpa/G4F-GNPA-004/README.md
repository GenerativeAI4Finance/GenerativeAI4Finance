# G4F-GNPA-004: Cost-sensitive risk evaluation

## Purpose

Calculate transparent false-negative and false-positive costs over user-supplied thresholds and user-supplied cost scenarios. This package is compatible with the binary labels and `score >= threshold` convention in [G4F-GNPA-003](../G4F-GNPA-003/README.md), including `new_npa_within_90d` or `stress_event_within_90d` from [G4F-GNPA-002](../G4F-GNPA-002/README.md).

The code reports arithmetic under declared assumptions. It does not prescribe a universally correct cost ratio, choose a threshold, define a credit policy, or recommend an action for a borrower.

## Cost definition

For positive class `pos_label` (default `1`):

- A **missed stress case** is a false negative (FN): actual positive, predicted negative.
- A **false alarm** is a false positive (FP): actual negative, predicted positive.
- `total_cost = FN × missed_stress_case_cost + FP × false_alarm_cost`.
- `cost_per_observation = total_cost / number_of_observations`.

Each `CostAssumption` requires a scenario name, per-case FN cost, per-case FP cost, cost unit, and rationale. Costs must be finite and non-negative, and at least one cost in a scenario must be greater than zero. They can be abstract units or values in a documented currency/unit; costs must use a common additive unit within each scenario. Results retain every assumption field so they can be recalculated and reviewed.

## Threshold behavior

The caller supplies every threshold. A score equal to the threshold is predicted positive (`score >= threshold`), consistent with G4F-GNPA-003. The report returns one row per cost scenario and threshold, with TP, FP, FN, TN, precision, recall, F1, false-positive rate, cost components, total cost, and normalized cost. It does not select or silently hard-code a threshold. Users should decide thresholds using their own validated operational assumptions and a declared validation set; do not tune on the final test set.

## Worked example

See [reports/worked_example.md](reports/worked_example.md). Its ten-case fixture is fictional and deliberately imbalanced. The cost values are illustrative synthetic units, not estimates of actual financial or operational harm. The example shows that changing assumptions changes which threshold has the lowest calculated cost; that result is specific to the fixture and assumptions.

## Use

From this folder:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

```python
from gnpa_costs import CostAssumption, cost_sensitive_threshold_report

assumptions = [
    CostAssumption(
        name="misses-cost-more",
        missed_stress_case_cost=5,
        false_alarm_cost=1,
        cost_unit="illustrative units",
        rationale="Example sensitivity case; replace with approved local assumptions.",
    ),
]
report = cost_sensitive_threshold_report(
    y_true, y_score, thresholds=[0.75, 0.50, 0.30],
    assumptions=assumptions, pos_label=1,
)
```

Drop censored/null labels before evaluation and keep labels and scores aligned to the same observations. `pos_label` identifies the stress/event class explicitly. Check more than one plausible cost scenario; no ratio should be presented as universally correct.

## Files

- `gnpa_costs/cost_analysis.py`: cost assumptions and threshold report calculation.
- `tests/test_cost_analysis.py`: arithmetic, class/threshold convention, and invalid-input tests.
- `reports/worked_example.md`: synthetic calculations under multiple assumptions.
- `requirements.txt`: pandas, NumPy, and pytest dependencies.
