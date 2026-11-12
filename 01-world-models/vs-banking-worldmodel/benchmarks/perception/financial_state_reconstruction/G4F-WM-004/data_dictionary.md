# Temporal Validation Fixture and Quality Report

## Input format

The validator accepts one JSON document:

- `dataset_id`: identifier for the input dataset.
- `synthetic`: whether the fixture is entirely synthetic.
- `records`: list of state observations.
- `splits`: one row per record assigning it to `train`, `validation`, or
  `test`.

Each record contains:

| Field | Meaning |
| --- | --- |
| `record_id` | Unique row identifier used to join split assignments. |
| `entity_id` | Borrower, business, loan, or other entity identifier. |
| `timestamp` | State observation time. The configured primary key is entity plus timestamp. |
| `state` | Discrete state validated against the allowed transition graph. |
| `features` | Map of feature name to `value`, `unit`, and `available_at` timestamp. |
| `outcome` | Optional future label and `observed_at` timestamp. |

Split rows repeat `record_id`, `entity_id`, `timestamp`, and `split`; the
validator checks those references against the source records. This general
fixture format is intentionally small and can be exported from borrower/loan
state records or scenario sequences produced by WM-001 through WM-003.

## Checks

The machine-readable report contains one result for each configured check,
with `pass`/`fail`, issue counts, diagnostic codes, and offending IDs:

- **Duplicate keys:** duplicate configured entity/time primary keys and
  repeated record IDs.
- **Missing timestamps:** absent or unparsable record timestamps.
- **Impossible transitions:** consecutive states for one entity that are not
  allowed by `allowed_state_transitions`.
- **Unit consistency:** feature units that differ from configured expected
  units.
- **Invalid ranges:** non-numeric values where a numeric range is configured,
  or values outside inclusive minimum/maximum bounds.
- **Future-data leakage:** feature `available_at` after the record timestamp,
  absent feature-availability timestamps, or outcomes observed at/before the
  record timestamp.
- **Split assignment integrity:** missing, duplicate, unknown, or mismatched
  split assignments and missing required splits.
- **Chronological split order:** maximum timestamp in each earlier split must
  be strictly earlier than the minimum timestamp in the next split.
- **Entity split separation:** when enabled, an entity cannot occur in more
  than one split.

Rules and thresholds live in `config/validation_rules.json`. Entity-disjoint
splits are enabled by default; disable this only when the evaluation protocol
intentionally allows an entity to appear across time partitions. The strict
chronological rule applies to the whole split, not merely to random row order.

## Fixtures and expected results

- `valid_temporal_dataset.json` passes all checks and demonstrates state
  transitions and entity-disjoint temporal splits.
- `invalid_temporal_dataset.json` intentionally includes duplicate IDs/keys,
  a missing timestamp, an impossible transition, unit and range violations,
  feature and outcome leakage, an entity crossing splits, and time-order
  leakage. Its report should fail and list each corresponding diagnostic.
- `reports/example_quality_report.json` is generated from the invalid fixture.

This validator checks metadata and configured structural rules. It cannot
prove that a feature is semantically free of future information, validate
economic meaning, or replace review of the split design and label construction.
