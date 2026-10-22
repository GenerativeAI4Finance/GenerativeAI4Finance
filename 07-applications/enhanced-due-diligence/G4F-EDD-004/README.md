# G4F-EDD-004: Synthetic EDD Case Dataset

## Overview

This package generates a versioned, deterministic dataset of fictional EDD cases. It includes synthetic companies, directors, shareholders, subsidiaries, addresses, jurisdictions, source records, and risk indicators. Five scenario types cover routine reviews, ambiguous entity matching, incomplete records, conflicting claims, and stale evidence.

**Every record is synthetic.** Names and addresses are visibly tokenized placeholders, registration IDs use `SYN`, and URLs use `example.org` placeholders. They do not identify real people or organizations, cite real evidence, or assert real allegations. Do not treat them as training labels about real-world risk.

## Contents

- `generate_dataset.py` — deterministic standard-library generator; no Faker data or network calls.
- `data/edd_cases_v1.json` — checked-in sample dataset, version `1.0.0`.
- `schema/dataset.schema.json` — dataset structure and synthetic-marker schema.
- `tests/test_generator.py` — reproducibility, coverage, uniqueness, and schema validation tests.
- `requirements.txt` — JSON Schema validation dependency.

Each dataset case contains a `case_record` conforming to the G4F-EDD-001 case schema, plus structured entity relationships, addresses, extended evidence provenance, and synthetic risk indicators. The `scenario` field identifies the data-quality situation being illustrated, not a judgment about a real entity.

## Data dictionary

| Field | Meaning |
| --- | --- |
| `dataset_name` | Dataset title. |
| `dataset_version` | Semantic version of the dataset format/content (`MAJOR.MINOR.PATCH`). |
| `seed` | Integer seed used by Python's `random.Random` for any selected values. |
| `synthetic` | Dataset-level marker, always `true`. |
| `generator` | Generator script name. |
| `case_count` | Number of case objects in `cases`. |
| `case_record` | EDD-001-compatible case summary with subject, jurisdiction, date, risk categories, minimal source records, findings, confidence, and review status. |
| `scenario` | One of `normal`, `ambiguous_entity_match`, `incomplete_records`, `conflicting_claims`, or `stale_evidence`. |
| `subject_entity` | Fictional company identity, registration placeholders, status, jurisdiction, and synthetic address list. |
| `directors` | Fictional person IDs, synthetic display labels, roles, and jurisdiction. Names are synthetic tokens, not realistic identities. |
| `shareholders` | Owner ID/type and ownership percentage; `null` indicates an intentionally missing value. |
| `subsidiaries` | Fictional related entity, jurisdiction, and ownership percentage. |
| `source_records` | Extended fictional source metadata including source type, title, publisher, placeholder reference, publication/access dates, status, summary, and provenance notes. |
| `risk_indicators` | Scenario indicator, evidence state, and synthetic explanation; not a real-world allegation or automated decision. |
| `synthetic` on an item | Explicit per-record marker for people, entities, addresses, and case bundles. |

### Source and evidence states

- `available`: placeholder source record exists in the fixture.
- `disputed`: the scenario intentionally includes inconsistent synthetic claims.
- `outdated`: the fixture's evidence date is deliberately old; it must not be read as current.

The EDD-001 `case_record.source_records` use the case schema's compact source shape. The additional `source_records` array preserves richer provenance/status fields for dataset exercises.

## Reproduce or generate another sample

From this directory, with Python 3.10 or newer:

```bash
python generate_dataset.py
```

The default command regenerates `data/edd_cases_v1.json` using seed `20261022`, two cases per scenario, and dataset version `1.0.0`. To choose a seed and output path:

```bash
python generate_dataset.py --seed 1234 --cases-per-scenario 3 --output data/edd_cases_custom.json
```

The same seed and generator version/arguments produce byte-for-byte equivalent JSON content. Python's seeded pseudo-random sequence is used only to select jurisdiction values; names, IDs, dates, descriptions, and scenario order are generated from fixed rules. Preserve the seed and generator version with derived datasets. When changing fields, scenario semantics, or generation rules, update the dataset version and review the schema and tests.

## Validate and run tests

Install the single validation dependency and run:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Tests confirm same-seed reproducibility, different-seed variation, dataset-schema validity, embedded EDD-001 case-schema validity, unique case IDs, synthetic markers, and coverage of all required scenario types.

## Scope and limitations

- This is a small fixture dataset for software, data-quality, and analyst-training exercises. It is not representative of actual customer populations, risk prevalence, financial-crime patterns, or any jurisdiction's registry.
- The jurisdiction codes are used as scenario attributes only; they do not imply that the synthetic names, addresses, companies, records, or allegations exist there.
- `example.org` URLs are placeholders and must never be cited as real evidence. Do not search for or infer a real subject from a synthetic label.
- The dataset does not encode legal thresholds or operational screening rules and must not be used to make customer, credit, compliance, or enforcement decisions.
- A scenario flag is designed test ground truth about the synthetic fixture only. It is not a real-world risk conclusion.
