# G4F-WM-009 Dataset and Evaluation Data Dictionary

## Frozen input panel

`data/sample/synthetic_panel.csv` is generated from
`G4F-WM-008/synthetic.py::make_panel(n_entities=60, n_periods=36,
horizon_months=3, seed=0)`. The data manifest records its row count and SHA-256.
This snapshot is included so ordinary model training does not need to import
the sibling WM-008 folder.

| Column | Meaning | Predictor use |
| --- | --- | --- |
| `entity_id` | Fictional panel entity key | Grouping only; not a model feature |
| `timestamp` | Prediction month `t` | Time split only |
| `utilisation` | Synthetic utilization-style feature at `t` | Included |
| `days_past_due` | Noisy synthetic days-past-due feature | Included; its source observation time precedes `t` |
| `income_ratio` | Synthetic income-related ratio at `t` | Included |
| `dpd_observed_at` | Synthetic timestamp when the DPD feature became available | Leakage metadata, not a feature; checked to be no later than `timestamp` |
| `default_in_horizon` | Whether latent synthetic stress crosses a threshold in the next three months | Target only |
| `recovery_amount` | Synthetic recovery amount generated conditional on future target | Excluded post-outcome field |

All values are synthetic. The panel generator uses a seeded random walk and
noise; see WM-008's `synthetic.py` for source-generation details.

## Evaluation report

- `split_summary`: row/entity counts and time coverage for train, validation,
  test, and purged rows.
- `overall`: metrics for both models by validation and test period.
- `test_by_quarter`: test metrics per calendar quarter.
- `test_by_utilisation_band`: test metrics for low (`<=0.50`), medium
  (`>0.50` to `<=0.80`), and high (`>0.80`) synthetic utilization.
- Each metric block includes sample size and target prevalence. ROC AUC and
  balanced accuracy are null for one-class groups; average precision is null
  when no positive rows exist.

Temporal split rule: training rows satisfy `timestamp + 3 months <=
validation_start`; validation rows start on/after validation start and satisfy
`timestamp + 3 months <= test_start`; test rows start on/after test start.
Rows in horizon-overlap gaps are dropped. This follows the time-purge principle
documented in WM-008.
