# G4F-WM-007: Causal Intervention Scenarios

This task provides a controlled synthetic environment for examining how
repayment terms, interest rates, credit limits, and collections timing affect
modeled cash flow and default outcomes. All intervention effects are generated
by documented equations; they are not estimated from observed borrowers.

## Contents

- `config/causal_scenarios.json` — seed, cohort ranges, risk-based baseline policy assignment, intervention arms, simulator coefficients, and counterfactual design.
- `schema/potential_outcome.schema.json` — JSON Schema for a potential-outcome record, with observational covariates, policy assignments, simulation context, and outcomes in separate fields.
- `simulator/causal_simulator.py` — cohort generation, intervention application, structural outcome equations, paired comparisons, and reproducible output writer.
- `data/sample/` — generated feature, policy and potential-outcome tables, illustrative records, model-implied effect summaries, and a hash manifest.
- `tests/test_causal_simulator.py` — deterministic replay, separation, intervention, paired-shock, and constraint tests.
- `research_note.md` — estimand, assumptions, confounders, counterfactual interpretation, and limitations.
- `data_dictionary.md` — field definitions and model equations.

## Generate the sample

From this folder:

```bash
python -m pip install -r requirements.txt
python -m simulator.causal_simulator
python -m pytest -q
```

The generator writes to `data/sample/` by default. Override paths with:

```bash
python -m simulator.causal_simulator --config config/causal_scenarios.json --output-dir data/sample
```

The simulator uses paired potential outcomes: each synthetic entity is
evaluated under the observed-policy control and every configured intervention,
with the same baseline covariates and exogenous shock across arms. Re-running
with the same seed and software/configuration produces the same tables.

## Relationship to earlier World Models tasks

WM-007's observational features follow the synthetic conventions in WM-002;
policy/outcome timing is aligned with WM-001's separation of information and
outcomes; scenario assumptions are explicit like WM-003; generated arms can be
represented as event-to-state interventions alongside WM-006; and data fields
are compatible with the general temporal validation concepts in WM-004 after
mapping to that validator's input format. WM-007 runs independently and does
not modify or import the earlier tasks.

The output is not a credit model, forecast, policy recommendation, or empirical
causal estimate. Only conclusions about the configured simulator are supported.
