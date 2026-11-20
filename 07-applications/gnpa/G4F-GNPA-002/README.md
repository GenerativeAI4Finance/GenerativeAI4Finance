# G4F-GNPA-002: Synthetic credit-risk labels

## Purpose and relationship to G4F-GNPA-001

This folder contains a reproducible synthetic account-history generator and point-in-time label builder. Its main outcome, `new_npa_within_90d`, follows the borrower-level, 90-calendar-day incident-target shape in [G4F-GNPA-001](../G4F-GNPA-001/README.md). Here, all values and outcomes are simulated; the generator's simplified NPA proxy is not an implementation of RBI classification rules and must not be represented as actual regulatory labels.

The output also provides two separate early-warning labels:

- `delinquency_30plus_within_90d`: any future observed snapshot with more than 30 days past due in the horizon.
- `stress_event_within_90d`: any future observed snapshot with the synthetic stress score at or above 0.70.
- `new_npa_within_90d`: first simulated transition into NPA status in the horizon, where the simulation proxy is `days_past_due > 90`.
- `cure_within_90d`: a future simulated transition from positive DPD to zero DPD in the horizon.

The horizon is `(observation_date, observation_date + 90 calendar days]`. Labels use future states by definition; model features contain only the snapshot values available at the observation date. Target, future event dates, and follow-up audit fields must not be passed to a model as predictors.

## Synthetic generation assumptions

- Every bank, borrower, account, date, balance, and event is generated fictionally. IDs are visibly prefixed `SYN-`; every row carries `is_synthetic=true`.
- A single account is generated per borrower so this small fixture does not simulate the borrower-level cross-facility propagation in RBI classification.
- Monthly observations are 30 calendar days apart. DPD increases by 30 days during simulated delinquency episodes and resets to zero in cure scenarios.
- Synthetic asset status changes to `npa` when DPD is greater than 90 and returns to `standard` after a simulated cure. This is only a transparent generator rule.
- A cure is explicitly recorded as `synthetic_cure_event` when DPD returns from a positive value to zero; its future-event label is `cure_within_90d`.
- Scenario probabilities intentionally yield an imbalanced population, with stable/low-stress paths more common than stress, delinquency and NPA paths. Exact class counts depend on the selected seed and borrower count.
- Each borrower receives an observation coverage end before or at the generated timeline's end. If an outcome event occurs during an incomplete horizon, it remains positive; if no event is seen and follow-up ends early, the label is null, not negative.
- This dataset is suitable for exercising code and label handling. It is not empirical evidence, a credit policy, or a production model dataset.

## Files

- `synthetic_gnpa/generator.py`: deterministic history generation and command-line entry point.
- `synthetic_gnpa/labels.py`: label definitions, point-in-time feature fields, and censoring logic.
- `synthetic_gnpa/validation.py`: synthetic-data, schema, label-range, and leakage checks.
- `tests/test_gnpa_labels.py`: deterministic, censoring, positive-event, and leakage tests.
- `data/account_history.csv`: generated time-indexed synthetic histories.
- `data/labeled_observations.csv`: features at observation time, target labels, and explicitly separated audit/outcome fields.
- `data/metadata.json`: dataset version and generation seed.

## Run

From this folder, install the dependencies and generate the versioned fixture:

```powershell
python -m pip install -r requirements.txt
python -m synthetic_gnpa.generator --borrowers 400 --seed 20261120 --output-dir data
```

Run validation tests from this folder:

```powershell
python -m pytest -q
```

To generate a different sample, set `--seed`, `--borrowers`, `--snapshots`, and optionally `--start-date`. Same arguments and dependency behavior produce the same data. Increment `DATASET_VERSION` when changing the schema or simulation assumptions, and regenerate the sample data and metadata together.

## Label and censoring rules

Only rows whose simulated status at the observation date is `standard` are eligible for labels. Rows already in simulated NPA status have null targets for all three outcomes, matching the incident-onset cohort approach of G4F-GNPA-001.

For each eligible observation, the labeler searches strictly after the observation date and through the horizon end. An observed event yields `1`, even when coverage ends before the horizon. No event yields `0` only when the account's `observation_coverage_end` reaches the horizon end; otherwise the result is null. NPA entry is based on the explicit `npa_entry_event` transition, so later cure does not erase the earlier entry event.

`FEATURE_COLUMNS` in `synthetic_gnpa/labels.py` is the allowed predictor list. Audit fields such as `first_npa_effective_date`, `cure_event_date`, `outcome_observed_through`, and `censor_reason`, as well as all targets, are outcome-only. `eligibility_status_at_t` is cohort metadata and should generally be used for filtering, not as a model predictor.

## Dataset version

The committed sample uses dataset version `1.0.0`, seed `20261120`, 400 fictional borrowers, and start date `2025-01-01`. It contains no real account or borrower data.

### Sample label balance

The committed 6,400-row sample has the following label counts. Null combines ineligible observations and incomplete follow-up; percentages are positive labels among non-null labels.

| Label | Positive | Negative | Null | Positive rate |
|---|---:|---:|---:|---:|
| `delinquency_30plus_within_90d` | 346 | 3,576 | 1,287 | 8.8% |
| `stress_event_within_90d` | 307 | 3,630 | 1,272 | 7.8% |
| `new_npa_within_90d` | 150 | 3,758 | 1,301 | 3.8% |
| `cure_within_90d` | 69 | 3,829 | 1,311 | 1.8% |
