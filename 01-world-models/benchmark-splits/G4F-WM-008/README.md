# G4F-WM-008: Benchmark splits and leakage checks

Build reproducible train/valid/test splits for a fictional or supplied panel,
then check common temporal and entity leakage risks. The bundled example uses
synthetic data; no real data is needed.

## Quickstart

```bash
cd 01-world-models/benchmark-splits/G4F-WM-008
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python example.py --policy time_entity --seed 7
python example.py --policy entity --out report.json
```

The example exits 0 only when every applicable check passes; a failure or an
applicable skipped check exits 1. It prints JSON unless `--out` is supplied.

## Input and split policies

Use a pandas DataFrame in long format: one row per entity and prediction time.
WM-001 has not landed; this module defines a small local contract.

| Field | Meaning |
| --- | --- |
| `entity_id` | Borrower, loan, or company identifier |
| `timestamp` | Prediction time `t`; datetime, consistently naive or timezone-aware |
| Features | Values known at or before `t` |
| Target | Outcome observed over `(t, t + horizon]`; numeric, with binary targets encoded 0/1 |
| `*_observed_at` | Optional timestamp for when a declared feature became known |

`(entity_id, timestamp)` must be unique, and ids and timestamps cannot be
missing. Configure columns and outcome timing with `PanelSpec`:

```python
PanelSpec(
    feature_cols=["utilisation", "days_past_due"],
    target_col="default_in_horizon",
    horizon=pd.DateOffset(months=3),
    post_outcome_cols=["recovery_amount"],
    observed_at={"days_past_due": "dpd_observed_at"},
)
```

A horizon is a finite, strictly positive pandas `DateOffset` or `Timedelta`
whose end is later than `t` on every row. Unsupported or overflowing calendar
arithmetic is rejected. An explicit embargo must be a finite, nonnegative
`Timedelta`; zero is valid. Time cutoffs must have the same timezone-awareness
as timestamps, and `valid_start` must precede `test_start`.

`make_splits(df, spec, policy, ...)` supports three policies:

- **`time`**: out-of-time evaluation; the same entity may occur in several
  splits. A row is train when `t + horizon + embargo <= valid_start`, valid
  when `t >= valid_start` and `t + horizon + embargo <= test_start`, and test
  when `t >= test_start`. Rows in the purge gaps are labelled `drop`. A row
  ending exactly at a cutoff stays in the earlier split; a row starting at a
  cutoff belongs to the later split.
- **`entity`**: out-of-entity evaluation; time is ignored and every row for an
  entity stays together. Its bucket is the first 8 bytes of
  `sha256("seed:id")`, interpreted in `[0, 1)`, with default fractions
  `0.7 / 0.15 / 0.15`. Assignment is stable when other entities are added or
  removed; group sizes are approximate, and rows are not balanced.
- **`time_entity`**: both rules apply; a row is kept only when its time window
  and entity group agree. Mismatches and purge-gap rows are `drop`. This is
  the strictest policy and the example default.

Rows labelled `drop` are excluded from training and scoring. All three
resulting splits must contain rows or `make_splits` raises `ValueError`. Entity
fractions must be three positive finite values summing to 1. Results depend on the input assignments, policy, cutoffs, horizon,
embargo, fractions, and seed, not row order.

## Checks and report interpretation

Call `run_checks(df, result.labels, spec, result.manifest)`. Checks cover split
sizes, entity overlap, near-duplicate trajectories, temporal ordering,
declared feature timestamps, declared and heuristic post-outcome fields, and
target leakage. Policy-inapplicable checks are skipped. A check that cannot
evaluate evidence is also `skipped`, never `pass`.

`ok` means no check failed, even if some checks were skipped.
`all_applicable_checks_passed` is the gate: it is true only if every required
check passed. The report includes `failed`, `skipped`, per-check status and
coverage, and a manifest with settings, row/entity counts, and
`assignment_sha256`. `feature_timestamps` is applicable when `observed_at` is
declared. A valued feature with a missing observation time fails; a valued
feature whose observation time is after `t` also fails. Undeclared feature
timestamps are trusted to represent values known at `t`.

The value-based post-outcome heuristic runs only for a binary target with at
least 10 positive and 10 negative kept rows. A check may otherwise be skipped
for insufficient coverage, such as fewer than 30 labelled rows for target
leakage, or no eligible cross-split trajectory alignment. Review the skipped
reasons and coverage; a skipped check is not evidence of safety. Declared
post-outcome columns and the target are still rejected as features when the
heuristic itself cannot run.

## Detection limits

- Target leakage checks look for copies (Cohen's kappa at least 0.85) and
  single features that nearly perfectly predict an unseen target (AUC or
  absolute rank correlation at least 0.99). Targets are shifted within each
  entity over its full history, including dropped rows; only kept feature rows
  contribute comparison evidence. Targets examined are the current row, the
  next 3 rows, and up to 12 earlier rows whose outcome windows remain open. These are row shifts within each entity, not calendar periods. A fully
  observed earlier target whose outcome window has closed can exempt a feature
  when it scores at least as well on the same rows. This is a value and timing
  heuristic, not provenance proof; multi-feature or weaker leaks, absent
  targets, and longer shifts are not checked.
- Near-duplicate checks compare whole entity histories, including dropped
  rows, ignoring absolute dates. Candidates come from exact rounded-history
  matches and 10 nearest entities by a fixed-length history summary. Histories
  align in time order with at most `max(1, floor(0.05 * longer_length))`
  unmatched rows, and match at RMS distance at most 0.1 panel standard
  deviations. Thus a 36-row history allows one unmatched row. Histories can
  be missed when more rows are absent, order changes, noise is larger, a copy
  is outside the candidate search, or fewer than 5 distinct rows are present.
  When no eligible candidate alignment exists, the result is skipped. Both
  scans use numeric features: the clone check lists nonnumeric and constant
  features under `ignored_features`; the target check lists unsupported,
  constant, or insufficiently paired features under `skipped_features`.
- `feature_timestamps` checks only features listed in `observed_at`; all
  others rely on the caller's declaration that values were known by `t`.
  Related entities are grouped only by `entity_id`, so affiliated borrowers
  can land in different entity splits. Fractions apply to entity counts and
  may produce uneven row counts; small panels can produce empty splits.
- Passing these smoke checks does not establish that data is leak-free or
  suitable for a credit or regulatory decision.

## Using the API and reproducing assignments

```python
from splits import make_splits
from leakage import run_checks, to_json

result = make_splits(
    df,
    spec,
    "time_entity",
    valid_start="2022-07-01",
    test_start="2023-04-01",
    seed=7,
)
report = run_checks(df, result.labels, spec, result.manifest)
print(to_json(report))
```

The assignment hash is SHA-256 over compact, sorted JSON records containing
native entity type, string value, timestamp, and split. Timestamps preserve
nanoseconds and UTC offsets; ids cannot create extra records by containing
separators. Hashes from earlier delimiter-based formats (including
microsecond or nanosecond variants) are not compatible, even when assignments
are the same. Keep the manifest and dependency versions with benchmark results.

Dependencies are pinned in `requirements.txt`. `panel.py` probes the private
pandas 3.0.6 `DateOffset._apply_array` capability to retain vectorized
arithmetic where supported, including DST behavior, and falls back to
Timestamp arithmetic otherwise. Recheck that probe when upgrading pandas.

## Validation

Run `python -m pytest -W error` from this directory; the 259-test suite includes
known-failure fixtures for temporal and entity leakage, clones, back-filled or
missing feature timestamps, post-outcome fields, copied or future targets, and
invalid inputs, alongside clean and skipped-coverage controls.
