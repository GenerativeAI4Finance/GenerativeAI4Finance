# G4F-WM-002: Synthetic Borrower and Loan-State Generator

Generates fully fictional borrower, loan, monthly financial-state, and
repayment-history tables for deterministic experiments. It includes normal
repayment, liquidity stress, persistent delinquency, cure, and default paths.

## Contents

- `config/generator.json` — versioned generation assumptions and fixed seed.
- `generator/borrower_generator.py` — NumPy/pandas generator and CSV writer.
- `data_dictionary.md` — fields, units, scenario behavior, and limitations.
- `data/sample/` — checked-in example CSV tables and a run manifest.
- `tests/test_generator.py` — reproducibility and data constraint tests.

## Generate the sample dataset

Run from this directory:

```bash
python -m pip install -r requirements.txt
python -m generator.borrower_generator
python -m pytest -q
```

The default command reads `config/generator.json` and writes the four CSV
tables and `manifest.json` under `data/sample/`. The same seed and configuration
produce the same rows. `manifest.json` records the seed, configuration hash,
runtime versions, row counts, and SHA-256 hashes of each output CSV. All IDs and data values are synthetic; they do not describe
real borrowers, loans, companies, or payment events.

## Scope

This is a controlled data fixture, not a calibrated credit model or estimate
of real-world default frequency. Scenario counts are specified directly in
configuration to ensure each path is present; they should not be interpreted
as population probabilities.
