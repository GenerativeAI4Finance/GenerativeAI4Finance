# G4F-WM-008: Benchmark splits and leakage tests

Split generator and leakage checks for world model panel data. Given a
panel of entities observed over time, it builds reproducible
train / valid / test splits and then checks the result for the usual ways
future information ends up in the training data.

Everything here runs on a small fictional borrower panel (`synthetic.py`).
No real data is used or needed.

## Input contract

WM-001 (the event and state schema) has not landed yet, so this task uses a
minimal contract of its own. It should be easy to map onto WM-001 once that
exists.

A pandas DataFrame in long format, one row per entity per prediction time:

| column | meaning |
| --- | --- |
| `entity_id` | borrower, loan or company id |
| `timestamp` | prediction time `t` (datetime) |
| feature columns | values known at or before `t` |
| target column | outcome observed over `(t, t + horizon]` |
| `*_observed_at` (optional) | when a feature value actually became known |

The columns are described with a `PanelSpec` (`panel.py`):

```python
PanelSpec(
    feature_cols=["utilisation", "days_past_due", "income_ratio"],
    target_col="default_in_horizon",
    horizon=pd.DateOffset(months=3),
    post_outcome_cols=["recovery_amount"],  # never allowed as features
    observed_at={"days_past_due": "dpd_observed_at"},
)
```

`(entity_id, timestamp)` must be unique, and `entity_id` and `timestamp`
must have no missing values.
`horizon` must be a pandas `DateOffset` or `Timedelta` whose window end is
finite and strictly later than its prediction timestamp on every row. Zero
and negative horizons are rejected. Unsupported or overflowing calendar arithmetic
raises `ValueError`. An
explicit `embargo` must be a finite, nonnegative pandas `Timedelta`.

## Split policy

Three policies. Pick the one that matches what the benchmark is meant to
measure and record it with the results.

**`time`** (out-of-time). Split by `valid_start` and `test_start`.

- train: `t + horizon + embargo <= valid_start`
- valid: `t >= valid_start` and `t + horizon + embargo <= test_start`
- test: `t >= test_start`

Rows in the gap before each boundary are dropped, because their labels
are only observed after the next split has started. A row exactly at a
cutoff belongs to the later split, and a row whose window ends exactly at
a cutoff still belongs to the earlier one. The same entity can appear in
every split. Use this when the question is "does the model work on later
periods for the same book". Cutoffs must be timezone-aware exactly when the
timestamps are, otherwise `make_splits` raises.

**`entity`** (out-of-entity). Each entity id is hashed together with the
seed (`sha256("seed:id")`, first 8 bytes read as a number in [0, 1)) and
placed by `fractions` (default 0.7 / 0.15 / 0.15): below 0.7 is train, below
0.85 is valid, the rest is test. Every row of an entity goes to one split
and time is ignored. Because the placement depends only on the seed and the
id, adding or removing other entities never moves an entity, which keeps a
refreshed benchmark comparable. The flip side is that shares are only
approximately the fractions (60 entities with 0.6 / 0.2 / 0.2 gave 37 / 13 /
10). Use this when the question is "does the model work on borrowers it has
never seen".

**`time_entity`** (both). Entities are grouped as above and time windows
are applied as in `time`. A row is kept only when the two agree (a train
entity in the train window, and so on). This drops a lot of rows but is
the strictest setup and the default in `example.py`.

Rows labelled `drop` are not for training or scoring. Their count is
in the manifest so it is visible how much data a policy throws away.

`make_splits` raises `ValueError` instead of returning a result when the
fractions (for the entity policies) are not three positive finite numbers
summing to 1, when a cutoff and the timestamps disagree on
timezone-awareness, when `valid_start >= test_start`, when `entity_id` or
`timestamp` has missing values, when `(entity, timestamp)` is duplicated,
or when train, valid or test would end up with no rows.
Invalid, zero or negative horizons and invalid or negative embargoes also
raise, under every policy. Zero embargo is supported.

The result is fully determined by the data, the policy, the cutoffs, the
embargo, the fractions and the seed. Row order does not matter.

## Checks

`run_checks` runs all of these. Each returns `pass`, `fail` or `skipped`.
`ok` in the report means only that nothing failed. It can be true when an
applicable check could not run, so it is not an overall pass.
`all_applicable_checks_passed` is true only when every check required by
the policy and declared feature timestamps passed. The `skipped` list
names all checks that did not evaluate anything, including checks that
do not apply to the selected policy.

| check | fails when | runs for |
| --- | --- | --- |
| `split_sizes` | train, valid or test has no rows | all |
| `entity_overlap` | an entity has kept rows in more than one split | `entity`, `time_entity` |
| `near_duplicate_trajectories` | two entities in different splits have feature histories that match within a tolerance (see below) | `entity`, `time_entity` |
| `time_order` | for an earlier split A and later split B, `max(t + horizon for t in A) > min_t(B)` | `time`, `time_entity` |
| `feature_timestamps` | a kept row with a feature value has an `observed_at` after its `t`, or no `observed_at` at all | all, if `observed_at` is set |
| `post_outcome_fields` | the target or a declared post-outcome column is a feature, or a feature looks like it is only set after the outcome | all |
| `target_leakage` | a feature copies the target, or predicts it almost perfectly (see below) | all |

**Near duplicates.** Features are z-scored with the panel's mean and std.
Each entity's whole history is compared, including rows labelled `drop`,
because under `time_entity` a copy keeps rows in other time windows than
the original. Candidate pairs are entities whose histories are identical
after rounding to 2 decimals, plus each entity's 10 nearest entities by a
fixed-length summary of the history. A candidate pair in different splits
is flagged when the two histories, aligned in time order with up to 5% of
rows (at least 1) left unmatched, differ by at most 0.1 standard deviations
(root mean square over matched rows). Absolute dates are ignored, so a copy
shifted in time still matches. Entities with fewer than 5 distinct rows
(dormant or very short histories) are not compared, since unrelated
entities look the same there; they are counted under `low_information`.
Non-numeric and constant features are ignored and listed under
`ignored_features`. The report lists up to 20 pairs and the total in
`n_pairs`.
`cross_split_candidates` counts candidate pairs assigned to different
splits; `aligned_pairs` counts those whose lengths permit an alignment.
When no cross-split pair can be aligned, the check is `skipped` with these
counts and a reason.

**Target leakage.** Targets are shifted within each entity over its full
history, including dropped rows, so purge gaps do not alter which target
belongs to a row. Only kept feature rows contribute evidence:

- `copies_target`: Cohen's kappa between the feature and a target it should
  not see is at least 0.85. Kappa is used rather than raw agreement so that
  two mostly-zero columns do not match just by both being mostly zero.
  Targets it should not see are this row's (shift 0), the next 3 rows of
  the same entity (shift 1 to 3), and up to 12 earlier rows whose outcome
  window is still open at this row's time (negative shift). An earlier
  target whose window has already closed is legitimately known, so a
  feature that agrees at least as well with one of those on the same rows
  is not flagged, including ties.
- `near_perfect_predictor`: against each of the same unseen targets, the
  feature alone has AUC of at least 0.99 in either direction (0/1 target),
  or absolute rank correlation of at least 0.99 (other targets). This
  catches noisy, scaled copies of upcoming targets. A fully observed lag
  that scores at least as well on exactly those rows exempts the feature
  here too. A lag missing on any compared row cannot provide an exemption.

Each suspect records the matched `shift`; a copy match takes precedence
over a predictor match for the same feature.

**Post-outcome values.** Besides the declared columns, for a 0/1 target
with at least 10 positive and 10 negative kept rows, a feature is suspect
when it differs from its usual value (the most common value on negative
rows, missing included) on at least half of the positive rows but on at
most 0.1% of the negative rows. That is the pattern of a collections flag or
recovery amount that only exists after the outcome. The report's
`value_check` says whether this part ran.

**Skipped, and failing for lack of evidence.** A check that could not
evaluate anything is `skipped` with a reason and coverage counts, never
`pass`:

- `target_leakage`: fewer than 30 labelled kept rows, a 0/1 target with
  fewer than 10 rows of a class, a constant target, or no feature that
  could be evaluated. Features dropped for being non-numeric, constant or
  too sparse are listed under `skipped_features`; evaluated ones under
  `features_evaluated`.
- `near_duplicate_trajectories`: no varying numeric feature, or fewer than
  2 entities with enough distinct rows, or no eligible cross-split
  candidate alignment (for example, informative entities exist only in
  train, or their history lengths differ too much).
- `feature_timestamps`: no `observed_at` declared, or no kept row has a
  value in a declared feature. A kept row with a feature value but a missing
  `observed_at` cannot be shown to be on time and counts as a failure, not a
  pass. Rows with no feature value need no timestamp. Per feature the report
  gives `rows_checked`, `late` and `unknown`.
- `time_order`: fewer than 2 splits with rows.
- `entity_overlap`: no kept rows.
- `entity_overlap`, `near_duplicate_trajectories` and `time_order` are also
  skipped when the policy does not call for them.

`post_outcome_fields` still checks the declared columns when its value
check is skipped.

`run_checks` also raises `ValueError` for missing columns, an empty panel,
missing entity ids or timestamps, non-datetime time columns, an
`observed_at` column whose timezone-awareness differs from `timestamp`,
labels with another index than the data, or unknown label values.

## Running

```bash
cd 01-world-models/benchmark-splits/G4F-WM-008
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m pytest
python example.py --policy time_entity --seed 7
python example.py --policy entity --out report.json
```

`example.py` exits with 1 if an applicable check fails or is skipped, so it
can be used as a CI gate. Skips for checks that do not apply to the selected
policy, or for undeclared feature timestamps, do not block the example.

scikit-learn is not needed: the nearest-neighbour search for near
duplicates is a short chunked numpy routine, and AUC and kappa are computed
directly. Dropping it avoids a slow import for a few dozen lines of code.

From your own code:

```python
from splits import make_splits
from leakage import run_checks, to_json

result = make_splits(
    df, spec, "time_entity", valid_start="2022-07-01", test_start="2023-04-01", seed=7
)
report = run_checks(df, result.labels, spec, result.manifest)
print(to_json(report))
```

## Report format

`run_checks` returns a plain dict that serialises to JSON:

```json
{
  "ok": true,
  "all_applicable_checks_passed": true,
  "failed": [],
  "skipped": [],
  "checks": {
    "time_order": {"status": "pass", "violations": []},
    "target_leakage": {"status": "pass", "suspects": [], "threshold": 0.99, "...": "..."}
  },
  "manifest": {
    "policy": "time_entity",
    "seed": 7,
    "fractions": [0.7, 0.15, 0.15],
    "valid_start": "2022-07-01T00:00:00",
    "test_start": "2023-04-01T00:00:00",
    "horizon": "<DateOffset: months=3>",
    "embargo": "0 days 00:00:00",
    "rows": {"train": 608, "valid": 84, "test": 90, "drop": 1378},
    "entities": {"train": 38, "valid": 12, "test": 10},
    "assignment_sha256": "b47fca86...",
    "spec": {"...": "..."}
  }
}
```

(Trimmed. The full output lists every check. These numbers are from
`python example.py --policy time_entity --seed 7`. With `--policy entity`
the split is 1368 / 432 / 360 rows with nothing dropped and `time_order` is
skipped; with `--policy time` the two entity checks are skipped.)

`assignment_sha256` hashes sorted JSON records containing the entity's
native type and string value, timestamp and split. JSON escapes pipes and
newlines in entity ids, so one id cannot imitate multiple assignment rows.
Timestamps preserve all nine fractional second digits and the UTC offset.
Hashes produced by either earlier delimiter format (microsecond or
nanosecond timestamps) will differ even when row assignments agree.
The fixed hash regression pins the new representation. Feature and schema
column names may include the checkers' former helper names such as `_entity`
and `_window_end`; the checks keep metadata outside the input columns.

## Historical measurements

Historical measurements from the earlier implementation, before the
regression fixes below, on the synthetic panel (60 entities, 36 monthly periods, 3 month
horizon, about 22% positive target) under `time_entity`, with a clone of a
random entity added under a new id that the hash puts in a different split
group, 30 panels with different seeds. Noise is independent per value, with
a standard deviation of the given share of each feature's std. These numbers
describe this synthetic data and will differ on real panels.

| clone of an entity | found |
| --- | --- |
| exact copy | 30 / 30 |
| noise 2% | 30 / 30 |
| noise 5% | 30 / 30 |
| noise 10% | 19 / 30 |
| scaled by 1.01 | 30 / 30 |
| one middle row dropped | 30 / 30 |
| first row dropped | 30 / 30 |
| dates shifted by 6 months | 30 / 30 |

With 200 entities (8 panels) every variant was found except 10% noise (6 / 8).
The detection limit sits near the 0.1 tolerance, by design.

False positives on the clean panels: `near_duplicate_trajectories` flagged
0 / 30 (0 / 8 with 200 entities), and the whole report failed 0 / 30 under
each of `time`, `entity` and `time_entity`.

Those measurements did not cover noisy shifted target copies or persistent
entity outcomes. They do not establish detection or false-positive rates
for those cases. Current regression tests cover noisy future-target scores
at shifts 1, 2 and 3, and fully observed three-month lags of persistent
binary and continuous outcomes, with and without score transformations,
under all three policies.

## Tests

210 tests run with `python -m pytest` on Python 3.12. Regression cases also
cover invalid and overflowing horizons, embargoes and cutoffs; nanosecond
hash differences for naive and timezone-aware data; delimiter and entity
type hash collisions; arbitrary helper names as feature and schema columns;
nullable numeric/text/boolean feature missing values; and zero cross-split comparison coverage.
An alignment regression ensures the total unmatched-row budget is enforced,
even when gaps on opposite sides cancel their displacement.
Time-order tests inspect every actual outcome-window end, including a valid
absolute-year offset whose window ends are not in prediction-time order,
and retain a relative-calendar-offset control.

`tests/test_splits.py` covers reproducibility (same seed, shuffled row
order, different seed), a fixed assignment hash, stable entity assignment
when other entities are added or removed, the purge gap, embargo, boundary
rows, whole-entity assignment, empty splits, bad fractions, timezone
handling, missing ids and timestamps, and input validation.

`tests/test_leakage.py` has a clean panel that must pass under all three
policies and known-failure fixtures for every check: an entity moved across
splits, six kinds of clone under `time_entity` (exact, noise, scaled, one
row dropped, first row dropped, dates shifted), a split with no purge gap,
back-filled and missing bureau timestamps, a post-outcome column and an
undeclared post-outcome value pattern, a copied target, a target joined from
two rows ahead, a lagged target that is and is not already observed, a rare
target, and a score that separates the target perfectly. It also has clean
controls (unrelated entities, dormant entities, an independent rare flag)
and cases for skipped results (tiny or one-sided data, text and empty
features), empty splits, bad labels and mismatched timezones.

## Limitations

- The target leakage sniff only catches copies, near copies and
  near-perfect single features. Leaks spread across several features, or
  ones that only lift performance a bit, will pass. It is a smoke test, not
  proof of a clean dataset.
- Lag exemptions rely on value similarity and observation-window timing,
  not feature provenance. When an unseen target is indistinguishable from
  an already observed lag, values alone cannot establish which supplied
  the feature. Shifts are row offsets, up to 3 forward and 12 backward;
  targets absent from the supplied panel and longer shifts are not checked.
- Near-duplicate detection assumes a copy keeps the same row order and at
  most about 5% of rows missing. The allowance is 5% of the longer history,
  rounded down, and never less than one row, so a 36-row history tolerates
  1 unmatched row: a copy with one row dropped is caught, one with 2 of 36
  dropped is missed. It is not widened because that would raise false
  positives. Heavier edits (noise above roughly 10% of a standard
  deviation, resampled or reordered history, several rows removed) are
  missed. Candidate pairs come from exact hashing and a 10-nearest
  neighbour search on a summary, so a copy whose summary is far from the
  original can be missed in a large panel. Entities with fewer than 5
  distinct rows are not compared.
- The `feature_timestamps` check only knows about features that declare an
  `observed_at` column. Everything else is trusted to be known at `t`.
- The post-outcome value heuristic needs a 0/1 target with 10 positives and
  10 negatives.
- Entity fractions are approximate and apply to entity counts, not row
  counts, so row shares vary when entities have very different history
  lengths. Very small panels can raise because a split ends up empty.
- Grouping is by `entity_id` only. Related entities (same group company,
  joint borrowers) are not linked and can still end up in different splits.
- Passing these checks does not mean a benchmark is fit for any regulatory
  or credit decision use.
