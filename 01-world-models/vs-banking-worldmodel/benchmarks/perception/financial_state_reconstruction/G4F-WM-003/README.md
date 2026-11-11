# G4F-WM-003: Synthetic Macroeconomic and Sector-Event Sequences

This self-contained generator creates deterministic fictional macroeconomic
paths and links selected rate, commodity, and sector-demand shocks to
synthetic business outcomes through documented simulation assumptions.

## Contents

- `config/scenarios.json` — seed, path settings, and sector-specific
  assumptions.
- `generator/macro_generator.py` — NumPy/pandas sequence generator, validator,
  and CSV writer.
- `data_dictionary.md` — fields, scenario definitions, formulas, and
  limitations.
- `data/sample/` — generated macro sequences, sector events, business outcomes,
  and a reproducibility manifest.
- `tests/test_macro_generator.py` — determinism and scenario relationship
  checks.

## Run

From this folder:

```bash
python -m pip install -r requirements.txt
python -m generator.macro_generator
python -m pytest -q
```

The generator writes CSVs to `data/sample/` by default. Use
`--config PATH --output-dir PATH` to generate another version. Generated
relationships are illustrative assumptions, not estimates or empirical facts
about economies, sectors, businesses, or borrowers.
