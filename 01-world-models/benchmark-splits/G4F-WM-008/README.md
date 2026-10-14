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

`(entity_id, timestamp)` must be unique.

## Split policy

Three policies. Pick the one that matches what the benchmark is meant to
measure and record it with the results.

**`time`** (out-of-time). Split by `valid_start` and `test_start`.

- train: `t + horizon + embargo <= valid_start`
- valid: `t >= valid_start` and `t + horizon + embargo <= test_start`
- test: `t >= test_start`

Rows in the gap before each boundary are dropped, because their labels
are only observed after the next split has started. The same entity can
appear in every split. Use this when the question is "does the model work
on later periods for the same book".

**`entity`** (out-of-entity). Unique entity ids are sorted, shuffled with
`numpy.random.default_rng(seed)` and cut by `fractions` (default
0.7 / 0.15 / 0.15). Every row of an entity goes to one split. Time is
ignored. Use this when the question is "does the model work on borrowers
it has never seen".

**`time_entity`** (both). Entities are grouped as above and time windows
are applied as in `time`. A row is kept only when the two agree (a train
entity in the train window, and so on). This drops a lot of rows but is
the strictest setup and the default in `example.py`.

Rows labelled `drop` are not for training or scoring. Their count is
in the manifest so it is visible how much data a policy throws away.

The result is fully determined by the data, the policy, the cutoffs, the
embargo, the fractions and the seed. Row order does not matter.

## Checks

| check | fails when | runs for |
| --- | --- | --- |
| `entity_overlap` | an entity has kept rows in more than one split | `entity`, `time_entity` |
| `near_duplicate_trajectories` | two entities in different splits have the same feature trajectory after z-scoring and rounding to 2 decimals (catches re-keyed copies) | `entity`, `time_entity` |
| `time_order` | for an earlier split A and later split B, `max_t(A) + horizon > min_t(B)` | `time`, `time_entity` |
| `feature_timestamps` | a declared `observed_at` time is after the row's `t` | all, if `observed_at` is set |
| `post_outcome_fields` | the target or a declared post-outcome column is listed as a feature | all |
| `target_leakage` | a feature equals the target (or the target of a later row of the same entity, up to 3 steps ahead) on 99% or more of rows, or predicts it almost perfectly on its own (AUC for a 0/1 target, rank correlation otherwise, threshold 0.99) | all |

Skipped checks are reported as `skipped` with a reason, not as `pass`.

## Running

```bash
cd 01-world-models/benchmark-splits/G4F-WM-008
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest tests
python example.py --policy time_entity --seed 7
python example.py --policy entity --out report.json
```

`example.py` exits with 1 if any check fails, so it can be used as a CI gate.

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
  "failed": [],
  "checks": {
    "time_order": {"status": "pass", "violations": []},
    "target_leakage": {"status": "pass", "suspects": [], "threshold": 0.99}
  },
  "manifest": {
    "policy": "time_entity",
    "seed": 7,
    "fractions": [0.7, 0.15, 0.15],
    "valid_start": "2022-07-01T00:00:00",
    "test_start": "2023-04-01T00:00:00",
    "horizon": "<DateOffset: months=3>",
    "embargo": "0 days 00:00:00",
    "rows": {"train": 672, "valid": 63, "test": 81, "drop": 1344},
    "entities": {"train": 42, "valid": 9, "test": 9},
    "assignment_sha256": "c4db5971...",
    "spec": {"...": "..."}
  }
}
```

(Trimmed. The full output lists every check.)

`assignment_sha256` is a hash of the sorted `(entity, timestamp, split)`
triples. If two runs give the same hash, they produced the same split.

## Tests

`tests/test_splits.py` covers reproducibility (same seed, shuffled row
order, different seed), the purge gap, embargo, whole-entity assignment and
input validation.

`tests/test_leakage.py` has a clean panel that must pass under all three
policies and a known-failure fixture for every check: an entity moved
across splits, a re-keyed copy of a borrower with tiny noise, a split with
no purge gap, back-filled bureau timestamps, a post-outcome column used as a
feature, a copied target, a target joined from two periods ahead, and a
score that separates the target perfectly.

## Limitations

- The target leakage sniff only catches copies and near-perfect single
  features. Leaks spread across several features, or ones that only lift
  performance a bit, will pass. It is a smoke test, not proof of a clean
  dataset.
- Near-duplicate detection is exact matching after rounding. A copy with
  noise larger than the rounding step, a different length, or reordered
  steps will not be found. Values sitting right on a rounding boundary can
  also hash differently.
- The `feature_timestamps` check only knows about features that declare an
  `observed_at` column. Everything else is trusted to be known at `t`.
- Entity fractions are applied to entity counts, not row counts, so row
  shares vary when entities have very different history lengths.
- Grouping is by `entity_id` only. Related entities (same group company,
  joint borrowers) are not linked and can still end up in different splits.
- Passing these checks does not mean a benchmark is fit for any regulatory
  or credit decision use.
