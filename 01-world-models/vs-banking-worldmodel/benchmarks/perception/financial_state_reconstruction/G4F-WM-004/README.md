# G4F-WM-004: Temporal Dataset Validation Suite

Validates time-series records for duplicate keys, missing timestamps,
impossible state transitions, inconsistent units, invalid value ranges,
future-data leakage, and train/validation/test split integrity. It emits a
machine-readable JSON quality report and includes valid and deliberately
invalid fixtures.

## Files

- `temporal_validation/` — validation engine and CLI.
- `config/validation_rules.json` — expected units, ranges, state transitions,
  and split rules.
- `fixtures/` — valid and intentionally invalid synthetic datasets.
- `reports/example_quality_report.json` — report generated from the invalid
  fixture to demonstrate failure reporting.
- `tests/` — checks for each rule and CLI output.
- `data_dictionary.md` — fixture format and rule definitions.

## Run

From this folder:

```bash
python -m pip install -r requirements.txt
python -m temporal_validation --input fixtures/invalid_temporal_dataset.json --output reports/example_quality_report.json
python -m pytest -q
```

The CLI exits with status 1 when validation failures are present and 0 when
all checks pass. The invalid fixture is expected to produce a failing report.
All fixture entities and values are fictional.
