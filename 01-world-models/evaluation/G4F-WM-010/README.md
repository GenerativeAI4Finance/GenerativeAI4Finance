# G4F-WM-010: Scenario prediction and calibration evaluation

Scores probability forecasts from a world model against held-out simulated
outcomes, with baseline, normal and stress scenarios reported separately.

There is no predictor (G4F-WM-009) or simulator output in the repo yet, so this
folder defines a small input contract and ships a seeded synthetic example. Once
WM-009 writes predictions in this format, the same command evaluates them.

## Input contract

Two CSV files joined on `entity_id, as_of, horizon, scenario`. Every prediction
must have exactly one outcome and the other way round, otherwise the run stops.

`predictions.csv`

| column | type | notes |
|---|---|---|
| `entity_id` | string | |
| `as_of` | date string | prediction time `t`; only information up to `t` should be used (see WM-001) |
| `horizon` | int | months after `as_of` |
| `scenario` | string | one of `baseline`, `normal`, `stress` |
| `p_event` | float in [0, 1] | probability of the binary event (e.g. default) within the horizon |
| `p_state_<name>` | float in [0, 1] | optional, probability of each next state; must sum to 1 per row |

`outcomes.csv`

| column | type | notes |
|---|---|---|
| `entity_id`, `as_of`, `horizon`, `scenario` | | same key as above |
| `event` | 0 or 1 | did the event happen within the horizon |
| `next_state` | string | required if `p_state_*` columns are given; must match one of the names |

Probabilities outside [0, 1], NaN, unknown scenario labels, duplicate keys and
unmatched rows are all rejected with an error.

## Metrics

All metrics are computed per scenario. `y` is the outcome, `p` the forecast, `N`
the number of rows.

- **Brier score**: `mean((p - y)^2)`. Lower is better.
- **Log loss**: `-mean(y log p + (1 - y) log(1 - p))`, with `p` clipped to
  `[1e-15, 1 - 1e-15]` so a confident miss is large but finite.
- **ROC AUC**: probability that a random event row gets a higher forecast than a
  random non-event row (ties count half). Measures ranking only, not calibration.
- **PR AUC**: average precision, the step-wise area under the precision-recall
  curve (same definition as scikit-learn). More informative than ROC AUC when
  events are rare.
- **Calibration in the large**: `mean(p) - mean(y)`. Negative means the model
  under-predicts.
- **ECE**: `sum_k n_k / N * |observed_k - mean_predicted_k|` over bins. Reported
  with two binnings:
  - equal-width (10 bins over [0, 1]): easy to read and compare across runs, but
    with rare events most rows land in the first bin;
  - equal-mass (10 quantile bins): every bin has about the same number of rows,
    so the estimate is less noisy where the forecasts actually are.
  If the two disagree a lot, look at the reliability table before trusting either.
- **Reliability table**: per bin, the row count, mean forecast and observed rate.
  Empty bins stay in the table with `n = 0` and null rates.
- **Murphy decomposition** of the Brier score over the equal-width bins:
  `Brier = reliability - resolution + uncertainty + within_bin`.
  `reliability = sum_k n_k/N (mean_predicted_k - observed_k)^2` (lower is better),
  `resolution = sum_k n_k/N (observed_k - base_rate)^2` (higher is better),
  `uncertainty = base_rate (1 - base_rate)`. The textbook identity is exact only
  when forecasts are constant inside each bin, so the leftover is reported as
  `within_bin` (Stephenson et al. 2008) and the parts always add up.
- **Next state** (if `p_state_*` given): multi-class Brier
  `mean(sum_c (p_c - 1[state = c])^2)` with range [0, 2], multi-class log loss,
  and top-1 accuracy.
- **Bootstrap intervals**: 95% percentile intervals from row resampling with a
  fixed seed, for Brier, log loss, ROC AUC, PR AUC and equal-width ECE.
  Resamples where a metric is undefined are dropped and counted in
  `undefined_draws`. ECE is biased upward under resampling, so for a well
  calibrated model the point value can sit below its interval.

If a scenario has only one outcome class, ROC AUC and PR AUC are `null` with a
reason, never 0 or 0.5. A scenario with no rows is reported as `null`.

There is also a breakdown by horizon inside each scenario (n, observed rate,
mean forecast, Brier) in the JSON.

## Why stress is reported on its own

A predictor fitted on calm periods tends to under-predict when conditions shift,
and stress rows are usually a minority. Pooled with baseline and normal rows the
miscalibration gets diluted and the headline number looks fine. So each scenario
gets its own row. `--pooled` adds a pooled view, but it is labelled as not a
headline number in both the JSON and the Markdown.

## How to run

```bash
cd 01-world-models/evaluation/G4F-WM-010
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python make_synthetic.py --seed 7 --out examples
python evaluate.py --predictions examples/predictions.csv \
    --outcomes examples/outcomes.csv --out reports/example_report
python -m pytest
```

Options: `--seed` (default 0), `--n-boot` (default 500), `--n-bins` (default 10),
`--pooled`.

## Report format

`evaluate.py` writes `<out>.json` and `<out>.md`. The JSON has:

- `metadata`: seed, bootstrap count, bins, log loss clip, sha256 of each input
  file, rows per scenario, numpy version
- `disclaimer`
- `scenarios.<name>.binary`: the metrics above, reliability tables for both
  binnings, Murphy terms and bootstrap intervals
- `scenarios.<name>.by_horizon` and `scenarios.<name>.state_transition`
- `pooled_all_scenarios` only with `--pooled`

There is no timestamp in the output, so the same inputs and seed give a
byte-identical report. The committed `reports/example_report.*` come from the
commands above.

## Synthetic example

`make_synthetic.py` makes fictional entities (`SYN-0000` and up; 300 in
baseline, 300 in normal, 200 in stress), two `as_of` dates and horizons of 6
and 12 months, with next states `current`, `delinquent` and `default`. The event is `next_state == default`. The predictor sees a noisy
risk score and assumes a mild shift for every scenario. In the stress scenario
the true default rate is shifted much higher and the predictor does not know,
so it under-predicts there on purpose. In the example report stress has an ECE
around 0.15 against about 0.01 for baseline, while ROC AUC barely moves: the
ranking still works, the probability level does not.

## Limitations

- Everything here is synthetic. The numbers say how well a predictor matches a
  simulator, not how it would do on real borrowers. Real-world validity needs
  validation on real outcome data, and passing these checks says nothing about
  regulatory compliance.
- The bootstrap resamples rows, not entities. If rows from the same entity are
  correlated (they will be in real panel data) the intervals are too narrow;
  a block or entity-level bootstrap would be the next step.
- ECE depends on the binning and is noisy with few events per bin. Read it
  together with the reliability table and the Brier decomposition.
- Only a binary event and a single next-state distribution are covered. Full
  trajectory or multi-step evaluation would need the WM-006 transition format.
- The scenario labels are fixed to `baseline`, `normal`, `stress`.
