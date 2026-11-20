# G4F-WM-007 Data Dictionary and Structural Model

## Data products and separation

| File | Grain | Contents |
| --- | --- | --- |
| `observational_features.csv` | One synthetic entity | Covariates fixed before policy assignment: income, income volatility, balance, balance-to-income months, and derived risk index. |
| `baseline_policies.csv` | One synthetic entity | Risk-based policy values assigned under the simulated observational policy: interest rate, term, credit limit, and collections delay. |
| `potential_outcomes.csv` | Entity × intervention arm | Effective intervention policy variables, shared exogenous shock, and simulated outcomes. |
| `example_potential_outcomes.json` | First three entities × all arms | Nested representation matching `schema/potential_outcome.schema.json`. |
| `model_implied_effects.json` | Intervention arm × outcome | Paired intervention minus control mean differences within the simulator. |

`observational_features` are generated before and remain unchanged across
intervention arms. Policy assignment/intervention values are kept separately
from those features. `simulation_context.shared_exogenous_shock` is a synthetic
random draw held constant for the same entity across all arms. Outcome fields
are never input as features.

## Feature and policy definitions

- `monthly_income_usd`: fictional monthly income drawn from the configured range.
- `income_volatility`: synthetic 0–1 volatility indicator.
- `balance_usd`: opening balance derived from income and a sampled balance-to-income duration.
- `balance_to_income_months`: opening balance divided by monthly income.
- `risk_index`: `clip(0.55 * balance_to_income_months / 5 + 0.45 * income_volatility / 0.35, 0, 1)`; a simulator covariate, not a real risk score.
- `interest_rate_pct`: annual nominal rate in percent.
- `term_months`: repayment term in months.
- `credit_limit_usd`: synthetic limit. Increased availability creates additional balance under the configured take-up assumption.
- `collections_delay_days`: days before the modeled collections action.

The risk-based observational policy assigns a rate of `5 + 15 * risk_index`,
a 24-month term for risk index ≥ 0.65 (otherwise 36 months), a limit of
`balance * (1.1 + 0.9 * (1 - risk_index))`, and a 15-day collections delay for
risk index ≥ 0.65 (otherwise 30 days). This intentionally creates treatment
selection related to observed risk covariates.

## Intervention arms

- `observed_policy`: unchanged risk-assigned policy; the within-entity control.
- `rate_reduction_2pp`: reduce annual rate by 2 percentage points, with a 2% floor.
- `term_extension_12m`: increase term by 12 months, capped by configured minimum/maximum.
- `limit_increase_20pct`: increase limit by 20%; increase balance by 10% of the added limit to represent assumed take-up.
- `collections_delay_plus_15d`: delay collections by 15 days.

Each non-control arm changes one policy dimension. The config records each
change explicitly. The simulator holds each entity's features and shock fixed
between arms.

## Structural equations

For balance `B`, annual rate `r` in percent, and term `n` months, monthly
payment `P` is the standard annuity payment:

`m = r / 1200`; `P = B*m / (1 - (1+m)^(-n))` (or `B/n` when `m = 0`).

Projected net cash flow is:

`income * (1 - 0.55 - 0.35 * income_volatility) - P`.

Monthly hazard is the logistic transform of:

`-6 + 3*(P/income) + 0.75*(B/income) + 1.3*income_volatility + 0.015*max(collections_delay_days - 15, 0)`.

The modeled horizon default probability is `1 - (1 - monthly_hazard)^horizon_months`.
The binary simulated default outcome is whether the shared uniform shock falls
below that probability. These coefficients, the hazard independence across
months, and the shared-threshold binary outcome are simplifying modeling
assumptions, not empirical estimates.

## Estimand and interpretation

For each arm/outcome, the summary is the mean within-entity difference between
that arm's potential outcome and the same entity's outcome under
`observed_policy`. It is a paired model-implied contrast under the configured
structural equations. The binary outcome difference is a simulated risk
difference across this synthetic cohort. Do not call these values real-world
causal effects, treatment effects, forecasts, or financial advice.

## Reproducibility and constraints

The manifest records seed, dataset/simulator versions, runtime versions,
configuration hash, output hashes, entity/arm counts, and generated record
count. Constraints include positive income, bounded volatility/risk, positive
terms, rates within configured bounds, non-negative credit limits and
balances, one row per entity-arm pair, and identical features/shock across
arms. Tests exercise determinism, these constraints, and expected controlled
changes.
