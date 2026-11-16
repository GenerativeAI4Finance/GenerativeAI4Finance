# G4F-WM-006 Data Dictionary and Transition Rules

## Dataset grain

Each row represents one event applied to one fictional entity at a timestamp.
The `initial_state` is the state immediately before that event; `resulting_state`
is the state immediately after it. Rows are ordered by `scenario_id` and
`sequence`. A row's resulting state must equal the next row's initial state
within the same scenario. Timestamps are strictly increasing within a path.

## Transition record fields

| Field | Meaning |
| --- | --- |
| `schema_version` | Record schema version (`1.0.0`). |
| `transition_id` | Stable synthetic transition identifier within this generated sample. |
| `scenario_id` | Identifier for the replayable trajectory. |
| `path_type` | One of `normal`, `stress`, or `recovery`. |
| `entity_id` | Fictional entity key prefixed `SYN-`. |
| `sequence` | One-based event order within the scenario. |
| `transition_timestamp_utc` | Event application time, encoded in UTC ISO 8601. |
| `event.event_type` | Event kind: scheduled payment, payment delay, liquidity shock, rate change, new credit exposure, recovery payment, or liquidity normalization. |
| `event.attributes` | Scalar event parameters after removing timestamp offset, type and action. |
| `action` | Optional simulated operational response; null when no action is taken. |
| `initial_state` | Complete state immediately before the event. |
| `resulting_state` | Complete state after deterministic event rules are applied. |
| `synthetic` | Always `true`; no real account or entity data is represented. |

State fields are `account_status`, `balance_usd`, `monthly_revenue_usd`,
`debt_to_income_ratio`, `days_past_due`, `interest_rate_pct`, and
`monthly_debt_service_usd`. The ratio is defined in this fixture as monthly
debt service divided by monthly revenue. USD and percentage units are
simulation conventions, not reported observations.

## Event behavior

| Event | Deterministic update |
| --- | --- |
| `scheduled_payment` | If received, subtracts payment amount from balance, floored at zero; status is current when no days are past due. |
| `payment_delay` | Adds configured days past due and sets status to delinquent. |
| `liquidity_shock` | Multiplies monthly revenue by the configured factor; sets current accounts to liquidity stress. |
| `rate_change` | Adds configured percentage points to rate and scales monthly debt service by new rate / old rate (when old rate is positive). |
| `new_credit_exposure` | Adds exposure to balance and configured monthly service to debt service. |
| `recovery_payment` | Subtracts payment amount from balance, clears days past due, and sets status to cured. |
| `liquidity_normalization` | Multiplies revenue by the configured factor; an account without arrears returns to current. |

After every event, dollar amounts are rounded to cents, rates to four decimal
places, and the debt-service/revenue ratio to six decimal places. Revenue must
remain positive; balance and debt service cannot be negative; interest rate
must remain between 0 and 100 percent. Status changes are limited to
`current`, `liquidity_stress`, `delinquent`, and `cured`, matching the relevant
WM-004 transition vocabulary. This simple generator does not model default or
charge-off.

## Reproducibility and validation

`config/transition_scenarios.json` supplies dataset and generator versions,
seed, initial-state value ranges, start timestamp, ordered event definitions,
and path type. The sample manifest records the seed, row/path/event counts,
configuration SHA-256 and output SHA-256 values. Generated output is stable
for the same configuration and compatible Python/NumPy/pandas environment.
Scenarios are replayable from an explicit initial state using
`replay_scenario(config, scenario, initial_state)`.

Schema-level constraints are in `schema/event_state_transition.schema.json`.
The generator checks supported event/path types and strictly increasing
positive event offsets when loading configuration. It rejects invalid rates
and nonpositive revenue while applying events. Review consumers should also
check cross-row continuity, unique IDs, timestamp ordering, and schema
conformance when loading modified or externally supplied records.

## Limitations

All entities, initial values, events, state changes, and actions are fictional.
The seed and coefficients provide repeatable software fixtures, not empirical
financial facts. In particular, the rate-to-debt-service proportional rule,
revenue multipliers, payment effects, initial ranges, and event schedules are
illustrative choices. The sample is too small and simplified to support
frequency estimates, causal conclusions, predictions, risk classifications,
or decisions about real entities.
