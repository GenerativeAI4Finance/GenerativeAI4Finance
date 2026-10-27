# G4F-EDD-007: Contradiction and Stale-Evidence Checks

This package compares analyst-structured observations from EDD evidence and
reports conflicting values, stale records, and evidence status concerns. It
preserves every supplied source reference and never selects a winning value.
All bundled records and identifiers are synthetic.

## How it fits the EDD workflow

- **EDD-001:** `observation_from_edd001` carries `source_id`, source type,
  description, and URL from a compact case source record. Since that format
  has no source check date, the caller must supply the actual check date from
  the case review context.
- **EDD-002:** `observation_from_edd002` carries `evidence_id`,
  `claim_reference`, optional `finding_reference`, title, URL, reference, and
  source type. It uses `access_date` for freshness and preserves the evidence
  status. `publication_date` is never treated as the check date.
- **EDD-006:** `observation_from_edd006` retains the candidate's full source
  reference and exact supporting passage. The caller supplies a structured
  value and the linked source's actual check date; model-generated text is not
  automatically promoted to a verified value.
- **EDD-003/004/005:** The output is designed for human-review workflows and
  synthetic/entity-resolution data. Subject IDs must be stable case-local
  identifiers; this module does not perform entity resolution, screening, or
  legal interpretation.

The three adapters require an analyst or upstream process to explicitly map a
source-backed observation to `subject_id`, `attribute`, and scalar `value`.
They do not infer structured values from excerpts, summaries, or candidate
sentences. An observation retains its originating source record and identifiers
so a reviewer can trace it back through the earlier tasks.

## Checks and decisions

Observations with the same `subject_id` and `attribute` are compared. Text
comparison trims whitespace and ignores case; finite numeric values compare as
numbers, so `60` and `60.0` are equivalent. Original values and all provenance
remain in the output. Other values are not aggressively normalized.

Freshness age is `as_of - checked_date` in calendar days. A record is stale when
its age is greater than the configured maximum, or its EDD-002 status is
`outdated`. A missing check date is reported as `checked_date_unavailable` and
also requires review. The checker does not use publication dates as a fallback.
Unavailable and disputed records appear in `evidence_status_issues` and require
human review. Contradictions always have status `conflicting_values` and
resolution `unresolved_requires_human_review`; even the newest or most
authoritative source is not chosen automatically.

The default thresholds are in `config/default.json`. Attributes not listed use
`default_max_age_days`. Set thresholds to fit institutional policy and the
underlying data source; defaults are illustrative, not regulatory standards.

## Use

```python
import json
from datetime import date
from evidence_checks import CheckConfig, review_evidence

with open("examples/synthetic_observations.json", encoding="utf-8") as file:
    fixture = json.load(file)

with open("config/default.json", encoding="utf-8") as file:
    config = CheckConfig.from_mapping(json.load(file))
result = review_evidence(fixture["observations"], as_of=date.today().isoformat(), config=config)
print(result)
```

The expected output contains `conflicts`, `stale_evidence`,
`evidence_status_issues`, and `requires_human_review`. Each conflict contains
every distinct value and the observations supporting it, with source references
and any EDD-006 passage locations intact.

## Tests

From this directory run `python -m pytest -q`. The tests cover company and
individual observations, EDD-001/002/006 adapters, numeric/text equivalence,
conflicting values, threshold boundaries, unknown dates, invalid dates, and
preservation of evidence provenance.

## Limitations

This is a deterministic comparison utility, not a source-authentication,
entity-resolution, ownership-calculation, sanctions-screening, or legal-review
system. Its results depend on the accuracy of the structured observations and
the selected freshness windows. It does not adjudicate conflicts, assume that a
newer source is correct, or establish the truth of a source claim.
