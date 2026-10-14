# G4F-WM-010: Scenario prediction and calibration evaluation

Scores probability forecasts from a world model against held-out simulated
outcomes, with baseline, normal and stress scenarios reported separately.

There is no predictor (G4F-WM-009) or simulator output in the repo yet, so this
folder defines a small input contract and ships a seeded synthetic example. Once
WM-009 writes predictions in this format, the same command evaluates them.

All results come from simulated data. They say how well a predictor matches the
simulator, not how it would perform on real borrowers. Real-world validity
needs validation on real outcome data.

## Input contract

Two CSV files joined on `entity_id, as_of, horizon, scenario`. Every prediction
must have exactly one outcome and the other way round, otherwise the run stops.

`predictions.csv`

| column | type | notes |
|---|---|---|
| `entity_id` | string | |
| `as_of` | date `YYYY-MM-DD` | prediction time `t`; only information up to `t` should be used (see WM-001) |
| `horizon` | whole number >= 1 | months after `as_of` |
| `scenario` | string | one of `baseline`, `normal`, `stress` |
| `p_event` | float in [0, 1] | probability of the binary event (e.g. default) within the horizon |
| `p_state_<name>` | float in [0, 1] | optional, probability of each next state; must sum to 1 per row |
| `from_state` | string | optional, state at `as_of`; adds a breakdown by starting state |

`outcomes.csv`

| column | type | notes |
|---|---|---|
| `entity_id`, `as_of`, `horizon`, `scenario` | | same key as above |
| `event` | 0 or 1 | did the event happen within the horizon |
| `next_state` | string | required if `p_state_*` columns are given; must match one of the names |

What is checked before anything is scored (each failure stops the run with a
`ContractError` that names the problem):

- required columns are present; prediction columns (`p_event`, `p_state_*`,
  `from_state`) are not in the outcomes file, outcome columns (`event`,
  `next_state`) are not in the predictions file, and no column other than the
  key is in both
- no missing values in the key; `scenario` is one of the three labels
- `as_of` is a real calendar date in `YYYY-MM-DD` form (`2025-02-30` and
  `2025-1-31` are rejected); date or timestamp objects are accepted and written
  as dates
- `horizon` is a whole number of months >= 1; `12`, `12.0` and `"12"` are the
  same horizon in both files, while `6.5`, `0`, negative numbers, text and
  booleans are rejected
- no duplicate keys, checked after the key is canonicalised, so `12` and `"12.0"`
  or `1` and `"1"` for an entity count as duplicates
- every prediction has exactly one outcome and the other way round
- `p_event` and `p_state_*` are numeric and in [0, 1] (NaN and inf rejected);
  `p_state_*` sums to 1 on every row; `event` is 0 or 1
- `next_state` is never missing and every value has a `p_state_` column
- if there is a `default` state, `p_event` must equal `p_state_default` and
  `event` must equal `next_state == default`, so the binary and multi-state
  views cannot disagree

## Metrics

All metrics are computed per scenario. `y` is the outcome, `p` the forecast, `N`
the number of rows.

- **Brier score**: `mean((p - y)^2)`. Lower is better.
- **Log loss**: `-mean(y log p + (1 - y) log(1 - p))`, with `p` clipped to
  `[1e-15, 1 - 1e-15]` so a confident miss costs about 34.5 instead of infinity.
  scikit-learn clips at machine epsilon (about 2.2e-16), so the two differ only
  for forecasts within 1e-15 of 0 or 1.
- **ROC AUC**: probability that a random event row gets a higher forecast than a
  random non-event row (ties count half). Measures ranking only, not calibration.
- **PR AUC**: average precision, the step-wise area under the precision-recall
  curve (same definition as scikit-learn). More informative than ROC AUC when
  events are rare.
- **Calibration in the large**: `mean(p) - mean(y)`. Negative means the model
  under-predicts.
- **ECE**: `sum_k n_k / N * |observed_k - mean_predicted_k|` over bins. Reported
  with two binnings:
  - equal-width (default 10 bins over [0, 1]): easy to read and compare across
    runs, but with rare events most rows land in the first bin;
  - equal-mass (10 quantile bins): every bin has about the same number of rows,
    so the estimate is less noisy where the forecasts actually are.
  If the two disagree a lot, look at the reliability table before trusting either.
- **MCE**: the largest `|observed_k - mean_predicted_k|` over non-empty bins
  (equal-width and equal-mass). It is usually set by one of the smallest bins,
  so the report prints that bin's row count next to the equal-width value.
- **Reliability table**: per bin, the row count, mean forecast and observed rate.
  Empty bins stay in the table with `n = 0` and null rates. The counts always
  add up to the number of rows; the code raises if they do not.
- **Murphy decomposition** of the Brier score over the equal-width bins:
  `Brier = reliability - resolution + uncertainty + within_bin`.
  `reliability = sum_k n_k/N (mean_predicted_k - observed_k)^2` (lower is better),
  `resolution = sum_k n_k/N (observed_k - base_rate)^2` (higher is better),
  `uncertainty = base_rate (1 - base_rate)`. The textbook identity is exact only
  when forecasts are constant inside each bin, so the leftover is reported as
  `within_bin` (Stephenson et al. 2008) and the parts always add up.
- **Debiased reliability**: the plug-in reliability above is pushed up by
  binomial noise in each bin's observed rate, even for a perfectly calibrated
  forecaster. Subtracting `observed_k (1 - observed_k) / (n_k - 1)` from each
  bin's squared gap removes that noise (Kumar, Liang and Ma 2019). It is not
  part of the Brier sum, and it can be slightly below 0 when the gap is within
  noise. A bin with one row keeps its plug-in term.
- **Next state** (if `p_state_*` given): multi-class Brier
  `mean(sum_c (p_c - 1[state = c])^2)` with range [0, 2], multi-class log loss,
  top-1 accuracy, and observed against mean predicted share per state. Each
  state also gets a one-vs-rest calibration block (Brier, ECE, MCE and
  reliability table of `p_state_<name>` against `1[next_state = name]`). If
  `from_state` is given, the same scores are repeated for each starting state.
- **By horizon**: inside each scenario, per horizon: n, events, observed rate,
  mean forecast, Brier and equal-width ECE.
- **Bootstrap intervals**: 95% percentile intervals from row resampling with a
  fixed seed (`--n-boot`, at least 1), for Brier, log loss, ROC AUC, PR AUC and
  equal-width ECE. Resamples where a metric is undefined are dropped and counted
  in `undefined_draws`. An interval that is undefined everywhere or has zero
  width is `null` with a `ci_null_reason`, never `[x, x]`.

If a scenario has only one outcome class, ROC AUC and PR AUC are `null` with a
reason, never 0 or 0.5. A scenario with no rows is reported as `null`.

### Binning rule

Equal-width edges are `k / n_bins`, computed so that each edge is the same
float as the decimal it stands for (0.3, not 0.30000000000000004). Bins are
`[lo, hi)`, except the last, which also takes 1.0. A forecast of exactly 0.3
therefore lands in `[0.3, 0.4)`. scikit-learn's `calibration_curve` uses
`(lo, hi]` bins with `np.linspace` edges, so a forecast that sits exactly on
an edge can land in a different bin. Everywhere else the two agree: the tests
compare the reliability tables on continuous forecasts for both the equal-width
and the quantile strategy. This is a deliberate choice, made so that a
forecaster that outputs values on a 0.1 grid is scored the same way whichever
way floating point rounds the edges. `--n-bins` and the library accept whole
numbers from 1 to 100; booleans, floats such as 2.5 or 10.0, text, zero and
negative numbers are rejected, on the command line (exit code 2, nothing
written) and in the library.

### Small-sample warnings

A scenario gets a warning, in the JSON (`scenarios.<name>.warnings`) and in the
Markdown, when it has fewer than 100 rows, fewer than 10 events, fewer than 10
non-events, or a next state with fewer than 10 observations, or when a bootstrap
interval has zero width. The thresholds are in `metadata.small_sample_minimums`.
They are rules of thumb, not a statistical test: below them the point values
are too noisy to read on their own. The Markdown marks such scenarios with
"(see warnings)".

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

Options: `--seed` (default 0), `--n-boot` (default 500), `--n-bins` (default 10,
1 to 100), `--pooled`. `--out` is a path without extension; a trailing `.json`
or `.md` is dropped and any other dot is kept.

## Report format

`evaluate.py` writes `<out>.json` and `<out>.md`. The JSON has:

- `metadata`: seed, bootstrap count, bins, log loss clip, small-sample minimums,
  sha256 of each input file (computed with CRLF read as LF, so a Windows copy
  hashes the same), rows per scenario, numpy version
- `disclaimer`
- `scenarios.<name>.warnings`
- `scenarios.<name>.binary`: the metrics above, reliability tables for both
  binnings, Murphy terms, debiased reliability and bootstrap intervals
- `scenarios.<name>.by_horizon` and `scenarios.<name>.state_transition`
  (`per_class` and `by_from_state` live inside the latter)
- `pooled_all_scenarios` only with `--pooled`

There is no timestamp in the output, floats are rounded to 10 significant
digits, and files are written with LF line endings, so the same inputs and seed
give a byte-identical report. The committed `reports/example_report.*` come
from the commands above; `.gitattributes` keeps the CSVs and reports at LF.

## Synthetic example

`make_synthetic.py` makes fictional entities (`SYN-0000` and up; 300 in
baseline, 300 in normal, 200 in stress), two `as_of` dates and horizons of 6
and 12 months, with next states `current`, `delinquent` and `default`. The
event is `next_state == default`. The predictor sees a noisy risk score and
assumes a mild shift for every scenario. In the stress scenario the true
default rate is shifted much higher and the predictor does not know, so it
under-predicts there on purpose.

Results from `reports/example_report.md` (seed 0, 500 resamples, 10 bins;
brackets are 95% bootstrap intervals):

| scenario | n | events | mean pred - observed | Brier | ROC AUC | ECE width | MCE width | reliability debiased |
|---|---|---|---|---|---|---|---|---|
| baseline | 1200 | 90 | 0.0059 | 0.0647 [0.0543, 0.0769] | 0.7404 [0.6871, 0.7979] | 0.0099 [0.0057, 0.0262] | 0.1998 (n=3) | -0.0008 |
| normal | 1200 | 112 | -0.0002 | 0.0772 [0.0655, 0.0892] | 0.7382 [0.6868, 0.7797] | 0.0062 [0.0067, 0.0270] | 0.3770 (n=6) | -0.0002 |
| stress | 800 | 198 | -0.1525 | 0.1945 [0.1731, 0.2180] | 0.7073 [0.6670, 0.7485] | 0.1531 [0.1259, 0.1835] | 0.4491 (n=2) | 0.0259 |

Stress has an ECE around 0.15 against about 0.01 for baseline and normal, while
ROC AUC barely moves: the ranking still works, the probability level does not.
The MCE values are set by bins of 2 to 6 rows and should not be read on their
own. No scenario triggers a small-sample warning.

The normal scenario's ECE point value (0.0062) sits just below its own interval.
That is expected: ECE adds up absolute gaps, so noise pushes it up, and each
bootstrap resample adds noise again. The debiased reliability for baseline and
normal is below 0, which says their remaining gap is within noise. The report
states this next to the table.

## Limitations

- Everything here is synthetic. The numbers say how well a predictor matches a
  simulator, not how it would do on real borrowers. Real-world validity needs
  validation on real outcome data, and passing these checks says nothing about
  regulatory compliance.
- The bootstrap resamples rows, not entities. Real panel data has several rows
  per entity (here two dates and two horizons) and they are correlated, so the
  intervals are too narrow; an entity-level or block bootstrap would be the next
  step. The debiased reliability also assumes independent rows.
- ECE and MCE depend on the binning and are noisy with few events per bin. Read
  them together with the reliability table and the Brier decomposition.
- The small-sample thresholds are fixed rules of thumb, not a power calculation.
- Only a binary event and a single next-state distribution are covered. Full
  trajectory or multi-step evaluation would need the WM-006 transition format.
- The scenario labels are fixed to `baseline`, `normal`, `stress`.
