# G4F-SW-007: Swarm AI + EDD Benchmark Scorecard

Defines and computes a transparent scorecard for synthetic EDD workflow runs.
Every metric is reported independently; this implementation does not calculate
a composite score. Missing or inapplicable measurements remain explicit and
are never silently converted to zero.

## Contents

- `scorecard_spec.md` — metric definitions, denominators, missing-value rules,
  and minimum reproducibility metadata.
- `schema/benchmark_run.schema.json` — JSON Schema Draft 2020-12 for benchmark
  input records.
- `config/scorecard.json` — versioned metric interpretation and citation rules.
- `scorecard/` — validated metric implementation and CLI.
- `examples/example_benchmark_run.json` — fictional input with source text,
  gold labels, predictions, and complete run metadata.
- `results/example_scorecard.json` and `.md` — generated example scorecard.
- `tests/test_scorecard.py` — metric, missing-value, schema, and reproducibility
  checks.

## Run

From this directory with Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m scorecard
python -m pytest -q
```

The example is self-contained and synthetic. No model endpoint, live evidence
source, or external service is accessed. The scorecard input contains the
annotated evidence and predictions needed to reproduce the example metrics.

## Interpretation

Read per-metric values, denominators, statuses, and notes before drawing a
conclusion. A scorecard may contain `not_available`, `not_applicable`, or
`partial` metrics. An explicit zero is used only when the measurement exists
and the observed numerator is zero. No overall score is emitted.
