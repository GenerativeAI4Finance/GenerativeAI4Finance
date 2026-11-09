# Data Dictionary

## Record grain and time convention

One record represents one entity at a prediction time, with an optional event
or action context. Timestamps use RFC 3339 date-time strings with a UTC `Z`
suffix in the examples. The prediction time `t` is the feature cutoff.

| Field | Type | Meaning | Timing / availability |
| --- | --- | --- | --- |
| `record_id` | string | Stable unique identifier for this observation. | Assigned when the record is created. |
| `entity_id` | string | Stable identifier for the synthetic or real-world entity in the consuming dataset. | Known at prediction time. |
| `entity_type` | enum | Entity category such as company, individual, or account. | Known at prediction time. |
| `prediction_time_utc` | date-time | Timestamp `t` at which a prediction or review would be made. | Defines the feature cutoff. |
| `event_timestamp_utc` | date-time or null | Timestamp of the event represented by this row, if event-triggered. | Must not be later than prediction time. |
| `event_type` | enum | Event context: scheduled review, payment, delinquency, balance update, or other. | Known at prediction time; use `none` for a pure state snapshot. |
| `action_taken` | enum | Action recorded at or before `t`, or `none` if no action was taken. | Historical/current action only; not a future decision. |
| `observation_source` | object | Origin and reference for the observed record. | Available at prediction time. |
| `target_horizon_days` | integer | Number of days after `t` over which outcomes are observed. | Declared before evaluation. |
| `features_at_t.as_of_utc` | date-time | Snapshot cutoff for feature values. | Must be at or before `prediction_time_utc`. |
| `features_at_t.values` | object | Closed set of numerical/categorical feature observations. | Inputs available by `t`; excludes labels and future outcomes. |
| Feature `value` | number, string, or null | Observed value. | `null` means no value was observed. |
| Feature `missing` | boolean | Explicit indicator for whether that feature value is missing. | Must be `true` exactly when `value` is null. |
| `outcomes_after_t.status` | enum | Whether the target horizon has completed and outcome was observed. | Label metadata; unavailable to the model at `t`. |
| `outcomes_after_t.observed_at_utc` | date-time or null | When the outcome was observed. | Must be after `t` and within the target horizon. |
| `outcomes_after_t.values` | object | Closed set of realized outcome labels. | Evaluation target only; never a feature. |

## Enumerations and units

- `entity_type`: `company`, `individual`, `account`.
- `event_type`: `none`, `scheduled_review`, `payment`, `delinquency`,
  `balance_update`, `other`.
- `action_taken`: `none`, `payment_received`, `payment_missed`,
  `limit_changed`, `review_completed`, `other`.
- `observation_source.source_type`: `synthetic`, `ledger`, `application`,
  `servicer`, `other`.
- Example feature units: `balance_usd` and `monthly_revenue_usd` are USD;
  `debt_to_income_ratio` is a decimal ratio from 0 through 1; `days_past_due`
  is a non-negative count; `account_status` is a controlled categorical value.
- Example outcomes: `default_within_horizon` is boolean and
  `realized_loss_usd` is a non-negative USD amount. These fields are
  illustrative and should be adapted to a documented task definition.

## Missing, unavailable, and pending values

For each feature, use `value: null` and `missing: true` when the value should
exist but was unavailable, not collected, or otherwise missing. Do not encode
missingness as zero, an empty string, or a sentinel number. If the feature was
not missing, set `missing: false` and provide a non-null value. A feature not
applicable to the entity should be represented as missing and its reason
recorded in the enclosing record's `quality_notes`.

When the target horizon has not completed, set outcome status to `pending`,
leave the observation timestamp null, and set outcome values to null with
missing indicators true. Do not infer a negative outcome from absence of a
record. In completed records, outcome values are observed after `t`.

`quality_notes` may document missingness, corrections, or caveats, but must not
be used to hide target labels in the feature block. Provenance references
identify input material; they do not certify its truth or quality.

## Leakage safeguards

1. Consumers must construct model inputs exclusively from `features_at_t`.
2. `outcomes_after_t` is reserved for labels, evaluation, or retrospective
   reporting and must not be passed to a prediction function.
3. Reject a row if feature cutoff or any individual observation timestamp is
   after `prediction_time_utc`; if the latter is tracked, enforce it in the
   ingestion pipeline because this schema stores feature-level values in a
   single snapshot.
4. Reject realized outcome timestamps at or before `t`, or later than the
   declared horizon end.
5. Keep feature definitions and label windows versioned with the dataset.

The schema prevents obvious structural leakage by making the feature and
outcome objects closed and distinct. It cannot prove the semantics of a
free-text note or verify all timestamp relationships; implement those checks
in the data pipeline.
