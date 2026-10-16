# G4F-EDD-001: EDD Case Schema

## Overview

This contribution defines a JSON Schema for a fictional Enhanced Due Diligence (EDD) case, includes fictional company, organization, trust, and individual examples, and checks valid and invalid data using Python.

**All sample data is fictional.** URLs use `example.org` placeholders and do not point to real case records. Do not add real personal, sensitive, or confidential information.

## Files

- `schema.json` — JSON Schema Draft 2020-12 definition.
- `examples/case_low_risk.json` — fictional company case in review.
- `examples/case_enhanced_review.json` — fictional organization case escalated for review.
- `examples/case_individual_low_risk.json` — fictional individual case with identity evidence.
- `examples/case_individual_review.json` — fictional individual case showing a possible name-only match that needs resolution.
- `examples/case_entity_trust.json` — fictional trust case with incomplete party and control information.
- `tests/test.py` — positive and negative validation tests.
- `requirements.txt` — Python dependency.

## Main fields

Required top-level fields:

- `case_id`
- `subject_type`
- `jurisdiction`
- `review_date`
- `risk_categories`
- `source_records`
- `findings`
- `confidence`
- `review_status`

Optional top-level field:

- `analyst_notes`

The schema also validates nested `source_records` and `findings`, enum values, date and URI formats, confidence from `0` to `1`, unique risk categories, and rejects unknown properties. An empty array is permitted for `risk_categories`, `source_records`, or `findings` because the schema does not impose a minimum item count.

## Allowed values

- `subject_type`: `individual`, `company`, `organization`, `trust`, `other`
- `review_status`: `pending`, `in_review`, `completed`, `escalated`
- `risk_categories`: `sanctions`, `politically_exposed_person`, `adverse_media`, `ownership_opacity`, `geographic_risk`, `financial_crime`, `identity_verification`, `other`
- Source `source_type`: `registry`, `sanctions_list`, `adverse_media`, `internal_record`, `identity_document`, `other`
- Finding `severity`: `low`, `medium`, `high`, `critical`
- Finding `disposition`: `unresolved`, `false_positive`, `substantiated`, `mitigated`

`jurisdiction` uses a two-uppercase-letter country code (ISO 3166-1 alpha-2 style). The regular expression checks the shape, not whether the code is officially assigned.

## Setup

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
```

Activate the environment:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux**
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run tests

From the `G4F-EDD-001` directory:

```bash
python -m unittest discover -s tests -v
```

The tests validate every JSON example and check that representative invalid cases are rejected with field-specific validation errors. Examples with individuals and entities are synthetic; a name-only hit is not treated as a confirmed identity match.

## Validate a JSON file manually

```python
import json
from jsonschema import Draft202012Validator, FormatChecker

with open("schema.json", encoding="utf-8") as file:
    schema = json.load(file)

with open("examples/case_low_risk.json", encoding="utf-8") as file:
    case = json.load(file)

validator = Draft202012Validator(schema, format_checker=FormatChecker())
errors = sorted(validator.iter_errors(case), key=lambda e: list(e.absolute_path))

if errors:
    for error in errors:
        field = ".".join(str(part) for part in error.absolute_path) or "<root>"
        print(f"{field}: {error.message}")
else:
    print("Case is valid.")
```

## Notes

- JSON Schema `format` checks for dates and URIs are activated by `FormatChecker` in the Python tests.
- The schema validates structure and values; it does not determine whether a risk allegation is true or make a compliance decision.
- Adjust enum values and naming to match the repository's existing conventions or maintainer feedback.
