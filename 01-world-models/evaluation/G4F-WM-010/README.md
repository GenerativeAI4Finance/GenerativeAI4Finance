# G4F-WM-010: Scenario prediction and calibration evaluation

Evaluates binary risk probabilities and next-state distributions against held-out
simulated outcomes. Baseline, normal and stress are reported separately, with
calibration, error analysis, metric definitions and reproducible JSON/Markdown.

WM-009 predictor and simulator outputs are not available in this repository, so
the example is synthetic. Its scores describe agreement with the simulator;
real-world validity requires validation on real outcomes. All bundled data and
simulator outputs are wholly synthetic/fictional; no root or applicable dataset
licence is declared. Maintainer guidance on an appropriate contribution and
dataset licence is requested.

## Run and reproduce

Use Python 3.12 and the pinned dependencies. From this directory:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python make_synthetic.py --seed 7 --entities-per-scenario 25 --out examples
python evaluate.py --predictions examples/predictions.csv \
    --outcomes examples/outcomes.csv --out reports/example_report \
    --seed 0 --n-boot 500 --n-bins 10
```

The continuation backslashes above are shell syntax for Linux/macOS; in PowerShell,
put the evaluation command on one line. The committed example uses 25 fictional
entities per scenario, two dates (`2025-01-31`, `2025-07-31`) and horizons of 6 and
12 months: 100 matched rows per scenario, 300 overall. Balanced scenario counts
keep each scenario visible in a compact review fixture. Omitting
`--entities-per-scenario` preserves the generator's default 300/300/200 entities
(3,200 rows); the full default panel remains covered by metric regression tests.

Evaluation defaults are seed 0, 500 bootstrap resamples and 10 bins. `--n-boot`
must be at least 1; `--n-bins` is an integer from 1 to 100. `--pooled` adds a view
labelled “not a headline number”: pooling can hide stress miscalibration. `--out`
is a path without extension; a trailing `.json` or `.md` is removed, other dots stay.

For DataFrames or existing files, the library uses the same contract and metrics:

```python
from scenario_eval.contract import join, load
from scenario_eval.report import evaluate, to_json, to_markdown

df = load("examples/predictions.csv", "examples/outcomes.csv")
# Or: df = join(predictions_dataframe, outcomes_dataframe)
report = evaluate(df, seed=0, n_boot=500, n_bins=10)
json_text, markdown_text = to_json(report), to_markdown(report)
```

## Input contract

Predictions and outcomes join one-to-one on `entity_id, as_of, horizon, scenario`.
`event` is the caller-supplied binary target measured at the specified horizon;
`next_state`, when supplied, is the state at that horizon. When the target is
default membership at the horizon, it equals default occurrence by that horizon
only if default is absorbing. Forecasts should use only information available at `as_of`.

| File | Columns | Meaning |
|---|---|---|
| Both | `entity_id`, `as_of`, `horizon`, `scenario` | Entity label; real `YYYY-MM-DD` date; positive int64 months; `baseline`, `normal` or `stress`. |
| Predictions | `p_event` | Finite real probability in [0, 1]. |
| Predictions, optional | `p_state_<name>` | Finite real probabilities in [0, 1], summing to 1 per row. |
| Predictions, optional | `from_state` | State at prediction time; enables a starting-state breakdown. |
| Outcomes | `event` | Binary 0 or 1, with booleans rejected. |
| Outcomes, conditional | `next_state` | Required with `p_state_*`; must name one of those states. |

Validation raises `ContractError` before scoring for missing keys/columns,
duplicate CSV headers, duplicate canonical keys, unmatched rows, invalid values,
or columns placed in the wrong file. Only key columns may occur in both files.
CSV empty fields are missing; literal labels `NA`, `NULL` and `nan` remain strings.
Dates must be real and exactly formatted; library date/timestamp objects become dates.
Horizons `12`, `12.0` and `"12"` canonicalise to the same value; fractions, booleans,
nonpositive values and values above 9223372036854775807 are rejected. Entity labels
also canonicalise before duplicate checks (`1` and `"1"` collide).

If a `default` state exists, `p_event == p_state_default` and
`event == (next_state == "default")` are required. CSV probabilities use round-trip
float parsing: values such as `1/6` retain their in-memory float and bin assignment.
The loader supports pandas' inferred compressed CSV formats as well as plain CSV.

## Metric definitions

Each scenario is scored independently. Let `y` be the event, `p` its forecast,
`N` the row count, and `w_k = n_k/N` for bin `k`.

| Metric | Definition and interpretation |
|---|---|
| Brier | `mean((p-y)^2)`; lower is better. |
| Log loss | `-mean(y log p + (1-y) log(1-p))`, clipped to `[1e-15, 1-1e-15]`. scikit-learn uses machine epsilon, so extreme forecasts differ. |
| ROC AUC | Probability an event ranks above a non-event, with half credit for ties; measures ranking. |
| PR AUC | Average precision, the step-wise precision-recall area used by scikit-learn. |
| Calibration in the large | `mean(p)-mean(y)`; negative means under-prediction. |
| ECE | `sum_k w_k * abs(mean_predicted_k-observed_k)`; equal-width and equal-mass bins are both reported. |
| MCE | Largest nonempty-bin absolute gap; the equal-width result includes the responsible bin's count. |
| Reliability table | Bin count, mean forecast and observed rate; empty bins retain count 0 and null rates, and counts sum to `N`. |
| Murphy decomposition | `Brier = reliability - resolution + uncertainty + within_bin`; see terms below. |
| Next state | Multi-class Brier `mean(sum_c (p_c-1[state=c])^2)` in [0, 2], log loss, top-1 accuracy, observed/predicted shares and one-vs-rest calibration. |
| Subgroups | Per-horizon event scores; state scores by `from_state` when supplied. |
| Intervals | Seeded 95% percentile row-bootstrap intervals for Brier, log loss, ROC AUC, PR AUC and equal-width ECE. |

Murphy reliability is `sum_k w_k (mean_predicted_k-observed_k)^2`, resolution is
`sum_k w_k (observed_k-base_rate)^2`, and uncertainty is `base_rate*(1-base_rate)`.
The `within_bin` residual makes the identity exact when forecasts vary inside a
bin (Stephenson et al. 2008). Debiased reliability subtracts
`observed_k*(1-observed_k)/(n_k-1)` from each squared gap (Kumar, Liang and Ma 2019);
singleton bins retain their plug-in term. It is separate from the Brier sum and
may be negative when the calibration gap is within sampling noise.

Equal-width edges are decimal-equivalent floats `k/n_bins`; bins are `[lo, hi)`,
with 1 included in the last. Exactly 0.3 enters `[0.3, 0.4)` with 10 bins.
scikit-learn's `calibration_curve` uses `(lo, hi]` and `np.linspace` edges, so
boundary forecasts can differ; continuous-forecast reliability is cross-checked
for both strategies. Equal-mass bins adapt to where forecasts occur. Read both
alongside counts, since ECE and MCE depend on binning and event scarcity.

A missing scenario is `null`. A single outcome class makes ROC/PR AUC `null`
with a reason. Bootstrap undefined draws are counted and dropped; wholly
undefined or zero-width intervals are `null` with `ci_null_reason`, never `[x, x]`.
Warnings appear in both outputs for fewer than 100 rows, 10 events, 10 non-events,
10 observations of any next state, or a zero-width interval. These thresholds
are rules of thumb, recorded in `metadata.small_sample_minimums`.

## Compact example results and provenance

The generator predicts from a noisy risk score with a mild assumed shift. Stress
raises the true default rate without informing the predictor. In this example,
the binary event is terminal default membership (`next_state == "default"`),
which is equivalent to default occurrence by the horizon only under an
absorbing-default simulator. Each horizon is sampled independently: these are
not path-coherent absorbing trajectories. The states are `current`,
`delinquent`, and `default`.
The commands above produce these results (brackets: 95% bootstrap interval):

| Scenario | n | Events | Mean pred - observed | Brier | ECE width |
|---|---|---|---|---|---|
| baseline | 100 | 3 | 0.0309 | 0.0305 [0.0055, 0.0617] | 0.0309 [0.0111, 0.0618] |
| normal | 100 | 8 | 0.0081 | 0.0576 [0.0290, 0.1000] | 0.0591 [0.0360, 0.1079] |
| stress | 100 | 17 | -0.0667 | 0.1374 [0.0918, 0.1887] | 0.0810 [0.0354, 0.1569] |

Baseline and normal trigger event/state-count warnings. Intervals overlap and
some MCE bins have only one row: this compact fixture demonstrates outputs and
warnings, and cannot establish statistically reliable scenario differences.
ECE's absolute gaps are biased upward by sampling noise; bootstrap resampling
adds noise again, so an ECE point estimate can lie below its percentile interval.

The JSON retains metadata, all scenario binary/state/horizon blocks and warnings.
Metadata records seeds, bins, bootstrap count, log-loss clip, row counts, NumPy
version and input SHA-256 hashes. CRLF is normalised to LF for hashing; matching
input basenames are prefixed with `predictions:`/`outcomes:`. The CLI captures each
file once and hashes exactly the bytes it parses, including compressed inputs.
There are no timestamps; JSON floats use 10 significant digits and outputs use
LF. Pinned dependencies, the same inputs and seeds reproduce both reports byte
for byte; artifact tests cover the public CLI, CSV golden bytes and CRLF copies.

## Development and limitations

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m ruff check --select S evaluate.py make_synthetic.py scenario_eval
python -m mypy
python -m pip check
```

Mypy checks all six runtime sources, including unannotated function bodies, with
pinned pandas stubs. The private pandas handle adapter uses a narrow protocol for
its tested text-reading interface. Tests also cross-check metrics with scikit-learn.

The bootstrap resamples rows, although dates/horizons repeat entities: dependence
can make intervals too narrow. Entity/block bootstrap would address panel data;
debiased reliability also assumes independent rows. Small samples and noisy bins
require caution. The fixed scenarios and one event/next-state distribution do not
evaluate full trajectories or establish regulatory compliance. Synthetic results
cannot establish performance on real borrowers without real outcome validation.
