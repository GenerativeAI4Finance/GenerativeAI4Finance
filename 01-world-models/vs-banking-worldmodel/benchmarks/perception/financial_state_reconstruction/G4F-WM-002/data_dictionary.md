# G4F-WM-002 Data Dictionary and Assumptions

## Dataset grain

The generator writes four CSV tables joined by stable synthetic IDs:

| File | Grain | Key fields |
| --- | --- | --- |
| `borrowers.csv` | One row per fictional borrower | `borrower_id`, `borrower_type`, annual income, synthetic region code |
| `loans.csv` | One row per borrower loan | `loan_id`, `borrower_id`, principal, rate, term, scheduled installment, scenario path |
| `monthly_states.csv` | One row per loan and observation month | state date, balance, income/expenses/cash flow, days past due, event/action, financial state |
| `repayment_history.csv` | One row per scheduled installment in the observation window | due/payment dates, scheduled/paid amount, payment status, days past due |

All money fields are USD. Rates are decimal annual rates; `month_index` is
zero-based from the configured start date. All date columns are ISO calendar
dates (the configured dates have no time-of-day component).

## Fields

### Borrowers

- `borrower_id`: stable synthetic borrower key (`SYN-BOR-####`).
- `borrower_type`: `individual` or `small_business`; type does not imply a real
  person or business.
- `annual_income_usd`: generated annual income from the configured uniform
  range.
- `home_region_code`: fictional `SYN-R##` grouping, with no geographic mapping.
- `synthetic`: always `true`.

### Loans

- `loan_id`: stable synthetic loan key; `borrower_id` references the borrower
  table.
- `origination_date`: one month before the first scheduled installment.
- `original_principal_usd`: generated amount within configured bounds.
- `annual_interest_rate`: generated fixed annual rate as a decimal.
- `term_months`: amortization term used to calculate a level scheduled payment.
- `scheduled_payment_usd`: fixed monthly payment using the standard amortizing
  loan formula; rounding is to cents.
- `scenario_path`: one of `normal_repayment`, `liquidity_stress`,
  `delinquency`, `cure`, or `default`.

### Monthly states

- `state_id`: unique loan/month snapshot key.
- `borrower_id`, `loan_id`: references to borrower and loan records.
- `state_date`, `month_index`: monthly due-date snapshot and zero-based month.
- `scenario_path`: the configured scenario assigned to the loan.
- `financial_state`: `current`, `liquidity_stress`, `delinquent`, `cured`, or
  `default`.
- `event_type`, `action_taken`: observed event and action at the snapshot;
  `loan_charged_off` is a synthetic action at default.
- `outstanding_balance_usd`: remaining principal plus modeled monthly interest
  accrued, less the principal component of posted payments.
- `monthly_income_usd`, `monthly_expenses_usd`, `net_cash_flow_usd`: current
  period cash-flow indicators; net cash flow equals income minus expenses.
- `days_past_due`: days from the oldest unresolved scheduled due date to the
  current state date, or zero when no installments are overdue.
- `synthetic`: always `true`.

### Repayment history

- `repayment_id`: unique synthetic installment key.
- `due_date`: configured scheduled installment date.
- `payment_date`: due date for on-time/synthetic cure payments; null when no
  payment was recorded.
- `scheduled_payment_usd`, `payment_amount_usd`: expected and recorded amounts.
  A cure installment may include the current scheduled amount plus one overdue
  installment.
- `payment_status`: `paid`, `missed`, `paid_late`, `defaulted`, or
  `not_due_after_default`. The overdue installment in a cure path is updated
  to `paid_late` with the later payment date; the current installment remains
  a separate `paid` row.
- `days_past_due_at_observation`: unresolved arrears age at that period's
  snapshot.

## Generation assumptions

The seed, observation window, scenario counts, ranges, and scenario month
indices are in `config/generator.json`. The default seed is `20261110`; changing
it changes the generated borrower/loan amounts while preserving the configured
scenario mix. The default configuration creates 16 borrowers and one loan per
borrower, with 6 monthly snapshots per loan.

- Income, expense share, principal, and annual rate are drawn from configured
  uniform distributions. No fitted or empirical borrower data is used.
- Expenses are generated once per borrower and held constant; liquidity stress
  reduces income to the configured multiplier during the configured months.
- A delinquency path misses the configured installments and remains
  delinquent during the sample window.
- A cure path misses an installment, then pays the current plus overdue
  scheduled amount in the configured cure month and returns to current. The
  arrears payment is represented on the original installment row as a late
  payment to keep installment-level totals interpretable.
- A default path misses installments; the synthetic charge-off state begins
  once days past due meets the configured threshold.
- Interest accrues monthly on outstanding balance; payments reduce principal
  by the amount remaining after that period's interest. The toy accounting
  omits fees, compounding conventions, partial payments, recoveries, and
  servicing adjustments.
- Scenario counts are deliberately fixed, not sampled from estimated
  population frequencies. They are test coverage quotas, not default rates.

## Reproducibility and validation

`manifest.json` captures the dataset and generator versions, fixed seed,
Python/NumPy/pandas versions, SHA-256 digest of the canonical configuration,
row counts, scenario counts, and SHA-256 digest of every output CSV. CSV outputs are
written in stable row order with fixed two-decimal formatting. The generator
and test suite check referential integrity, unique IDs, non-negative balances
and payments, valid dates, synthetic markers, required scenario coverage, and
default timing. Identical Python, NumPy, pandas, configuration, and seed
versions are expected to produce identical CSV bytes.

The data is for software tests and demonstrations only. It is not a forecast,
credit score, calibrated portfolio, or evidence about real borrowers.
