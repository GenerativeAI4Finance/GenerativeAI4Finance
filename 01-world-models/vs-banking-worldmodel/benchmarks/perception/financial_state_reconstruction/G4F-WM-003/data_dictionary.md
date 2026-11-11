# G4F-WM-003 Data Dictionary and Simulation Assumptions

## Dataset grain

Four generated CSV tables share stable synthetic business IDs and scenario
dates:

| File | Grain | Purpose |
| --- | --- | --- |
| `businesses.csv` | One row per synthetic business | Business ID and assigned sector. |
| `macro_sequences.csv` | One row per scenario, month, and sector | Fictional policy rate, commodity index, aggregate demand index, sector demand index, and event label. |
| `sector_events.csv` | One row per sector at each stress event start | Human-readable event and configured shock magnitudes. |
| `business_outcomes.csv` | One row per business, scenario, and month | Simulated revenue, operating cost, debt service, cash flow, and stress flag. |

Every output row has `synthetic=true`. Every macro/event/outcome row has
`relationship_type=simulation_assumption`. Dates are month-end ISO dates;
`month_index` is zero-based. Index values are dimensionless and initialized
near 100. The policy rate is in percent, and shock changes are expressed in
percentage points or percent as named.

## Scenario definitions

`config/scenarios.json` contains the fixed seed, date range, sectors,
assumptions, and scenario magnitudes.

- **Baseline:** seeded variation around the initial policy-rate, commodity,
  aggregate-demand, and sector-demand indices. It has no discrete sector event.
- **Stress:** begins at `shock_start_month_index`. It applies a rate increase,
  commodity-price increase, aggregate-demand reduction, and sector-specific
  demand changes from that month onward. Sector event names are configured by
  sector.
- Both scenario paths share the same generated underlying baseline sequences
  and synthetic business characteristics, so the stress comparison isolates
  the configured changes from random baseline differences.

The scenario counts are controlled, not estimated frequencies. The seed is
`20261111`; changing it changes small monthly fluctuations and business
characteristics while keeping scenario definitions fixed.

## Explicit simulation assumptions

All of these relationships are modeling choices for synthetic examples, not
empirical financial facts:

1. The policy rate follows a seeded random walk around the configured starting
   value. Under stress, a fixed configured percentage-point change is added
   from the shock month onward.
2. The commodity-price index follows a seeded multiplicative random walk. A
   configured proportional increase is applied in the stress scenario.
3. Aggregate demand and each sector's demand index vary using seeded noise.
   Configured percentage changes are applied from the stress start.
4. Business revenue index is:
   `base_revenue_index * sector_demand_index / 100 * (1 + commodity_revenue_sensitivity * (commodity_price_index / 100 - 1))`.
5. Operating cost index is:
   `base_revenue_index * operating_cost_share * sector_demand_index / 100 * (1 + commodity_cost_sensitivity * (commodity_price_index / 100 - 1))`.
6. Debt service index is:
   `base_revenue_index * baseline_debt_service_share * (policy_rate_pct / base_policy_rate_pct) ** rate_sensitivity`.
7. Modeled cash flow is revenue minus operating costs minus debt service.
   `cashflow_stress_flag` is true when it is at or below the configured
   synthetic threshold (16 index points by default; an illustrative buffer,
   not a calibrated risk boundary). `cashflow_change_vs_baseline_index` compares the same
   business and date across the two scenarios.

Sector sensitivities and shocks are synthetic coefficients chosen to make
scenario effects inspectable. They are not estimates from borrower, company,
market, or macroeconomic data. No causal or predictive claim is made.

## Columns

### `businesses.csv`

- `business_id`: stable fictional key (`SYN-BIZ-...`).
- `sector`: configured sector category.
- `synthetic`: always true.

### `macro_sequences.csv`

- `scenario`: `baseline` or `stress`.
- `date`, `month_index`, `sector`: sequence coordinates.
- `policy_rate_pct`: simulated policy-rate level in percent.
- `commodity_price_index`: synthetic price index.
- `aggregate_demand_index`, `sector_demand_index`: synthetic demand indices.
- `sector_event`: configured stress event label or `none`.
- `relationship_type`: always `simulation_assumption`.

### `sector_events.csv`

- `event_id`, `scenario`, `date`, `sector`: synthetic event identity and timing.
- `event_name`: configured descriptive event label.
- `policy_rate_change_pct_points`, `commodity_price_change_pct`,
  `sector_demand_change_pct`: configured shock magnitudes, not measured changes.
- `relationship_type`: always `simulation_assumption`.

### `business_outcomes.csv`

- `business_id`, `scenario`, `date`, `month_index`, `sector`: join keys.
- `revenue_index`, `operating_cost_index`, `debt_service_index`: formula outputs.
- `modeled_cashflow_index`: revenue less operating costs and debt service.
- `cashflow_change_vs_baseline_index`: same business/date stress minus baseline.
- `cashflow_stress_flag`: threshold indicator, not a default/credit decision.
- `relationship_type`: always `simulation_assumption`.

## Reproducibility and limits

The manifest records dataset/generator versions, seed, Python/NumPy/pandas
versions, canonical configuration SHA-256, CSV output SHA-256 values, row
counts, and scenario counts. The generator preserves row order and fixed
decimal formatting. Reproduction is expected with the same software versions,
configuration, and seed.

This small dataset demonstrates a simulation pipeline. It is not calibrated,
does not use observed market data, does not represent real borrowers/businesses,
and must not be interpreted as a financial forecast or sector-risk estimate.
