# Model Card: G4F-WM-009 Synthetic Financial State Predictor

## Summary

- **Model:** `StandardScaler` followed by class-weighted scikit-learn logistic regression (`C=1`, `max_iter=1000`, seed 42).
- **Comparator:** `DummyClassifier(strategy="most_frequent")`, fitted only on training labels.
- **Dataset:** Frozen synthetic panel exported from `G4F-WM-008`, 60 fictional entities and 36 monthly prediction times (2,160 rows).
- **Version:** Dataset 1.0.0; evaluation 1.0.0. Exact data/config hashes and package versions are saved in `reports/run_manifest.json`.

## Intended use

Demonstrate a simple baseline training/evaluation workflow for a time-indexed,
synthetic financial-state label. Appropriate uses include software examples,
teaching, and method smoke checks. The model is not intended for underwriting,
collections, account management, customer-level decisions, or deployment.

## Target and prediction horizon

At timestamp `t`, predict `default_in_horizon`: whether the source panel's
synthetic latent stress process exceeds its configured threshold during any of
the following three monthly periods. It is a simulator-defined label, not
observed default or loss.

## Inputs and leakage controls

The model uses `utilisation`, `days_past_due`, and `income_ratio` from time `t`.
`default_in_horizon` is the target and is never a feature. `recovery_amount` is
post-outcome data and is excluded. The three-month outcome window is purged
before validation and test cutoffs. The source panel records the observation
time for `days_past_due`; it predates `t`.

## Evaluation

Evaluation is out-of-time: train labels whose horizons end by 2022-07-01,
validation labels whose horizons end by 2023-04-01, and test rows timestamped
from 2023-04-01 onward. Time splits intentionally allow the same entity to
occur in train, validation, and test, so results measure later-period
performance on the same synthetic entities, not generalization to unseen
entities. The logistic model is compared with the training-only most-frequent
class baseline. Metrics include accuracy, balanced accuracy, precision, recall,
F1, ROC AUC, average precision, Brier score, support, and positive rate.
Undefined class-dependent metrics are null. Test results are broken out by
quarter and utilisation band; small subgroup estimates are noisy.

See `reports/baseline_metrics.json` for measured results and group counts.

On the bundled synthetic test split (540 rows), logistic regression achieved
accuracy **0.8778**, balanced accuracy **0.8778**, precision **0.7933**, recall
**0.8777**, F1 **0.8333**, ROC AUC **0.9511**, and Brier score **0.0868**. The
majority-class baseline achieved accuracy **0.6519**, balanced accuracy **0.5**,
F1 **0**, ROC AUC **0.5**, and Brier score **0.3481**. These figures describe
only this generated panel and split; they are not estimates of real-world
performance.

## Training data and synthetic construction

The source generator creates stress random walks, noisy features, and a
future-horizon threshold label. Synthetic recovery amounts are generated
conditional on the future label and therefore demonstrate why post-outcome
fields must be kept out of features. No real borrower or account data is used.

## Limitations and risks

- The synthetic process is deliberately simple and its label is generated from
  a latent stress process; results cannot be interpreted as real-world
  predictive performance or financial risk.
- One small synthetic panel, one temporal cutoff, one feature set, and one
  un-tuned model are insufficient to establish robustness.
- Evaluation is not entity-disjoint and does not establish performance on
  unseen borrowers, institutions, geographies, economic regimes, or data
  collection processes.
- The utilization subgroup is a synthetic slice, not a fairness or protected
  group analysis. No fairness conclusion is supported.
- Threshold 0.5 and class weighting are illustrative choices; no operational
  threshold or cost-sensitive decision rule is recommended.
- Passing the included checks establishes reproducibility and selected
  leakage safeguards only; it does not prove the panel is leak-free or suitable
  for a consequential use.
