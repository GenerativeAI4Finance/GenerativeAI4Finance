# G4F-EDD-008: Auditable EDD Report Generator

Generate a Markdown report from structured EDD case, evidence, extraction, and
evidence-review data. The report preserves source identifiers and provenance,
separates extractor output from case findings, and explicitly shows missing or
unresolved information. It does not generate an overall accusation, risk rating,
or automatic final decision.

## Compatibility with earlier EDD tasks

- **EDD-001:** Reads the existing `case_record` fields, including case ID,
  subject type, jurisdiction, review date, compact source records, findings,
  severity, disposition, and review status. The EDD-001 schema does not connect
  a finding directly to a source; the report does not assume that every source
  in the case supports every finding.
- **EDD-002:** Accepts evidence records and links them to an EDD-001 finding
  only through the optional `finding_reference` field. The record's evidence
  ID, claim reference, title, publisher, URL/reference, dates, source class,
  status, excerpt/summary, provenance, and limitations are retained. Records
  classified as generated alone do not support a substantive case finding.
- **EDD-004:** Accepts its nested `case_record` bundle and reads
  `dataset_version` and the synthetic marker when the bundle is supplied.
  A full EDD-004 dataset may be passed to the Python API; use
  `dataset_case_index` to select one case for a report.
- **EDD-006:** Accepts the structured extraction result. Candidates with exact
  evidence quote and source reference appear in a separate section unless the
  source reference explicitly links them to an EDD-001 `finding_id`. Inferences,
  extracted facts, and unresolved outputs remain labeled as extractor/model
  candidates and retain their human-review status.
- **EDD-007:** Accepts the contradiction/staleness result and carries conflicts,
  stale records, source status issues, unresolved questions, and review actions
  into the report without resolving them.

An EDD-001 case finding is included in the substantive findings section only
when an EDD-002 record links to its `finding_id`, is not marked unavailable, and
is not classified as generated, or an EDD-006 candidate links by
`finding_reference` and is an exact source claim accepted as
`source_backed_candidate`. Inferences and generated-only material never
independently support a substantive finding. Otherwise the summary is withheld
and the report lists the finding ID/category with an explicit missing-evidence
issue. The report does not infer links by matching names or by proximity in an
input array.

## Input bundle

`examples/report_input.json` demonstrates this JSON bundle:

| Key | Contents |
| --- | --- |
| `case_record` | EDD-001 case object; may also be an EDD-004 case bundle containing `case_record` |
| `evidence_records` | EDD-002 records, linked using `finding_reference` |
| `source_records` | Optional EDD-001 compact source records (or use `case_record.source_records`) |
| `subject_entity` | Optional EDD-004 entity identity fields used to fill display name and subject ID absent from EDD-001 |
| `extraction_result` | Optional EDD-006 extraction output |
| `evidence_review` | Optional EDD-007 result |
| `scope` | Review scope supplied by the analyst |
| `unresolved_questions` | Explicit open questions |
| `limitations` | Additional analyst-recorded caveats |
| `recommended_actions` | Human-review steps supplied by the analyst |
| `report_version` | Report format/version identifier |
| `dataset_version` | Dataset version; reported as “Not provided” when absent |
| `generated_at` | Optional ISO-8601 timestamp with timezone; normalized to UTC |
| `synthetic` | Optional fixture marker |

Missing values are printed as `Not provided` or explained in the relevant
section. A missing finding link is not treated as evidence that no issue exists.
Case summaries are labeled as supplied and not independently verified. An
EDD-002 `excerpt_or_summary` is described as a source-record excerpt/summary,
not represented as a direct quote. EDD-006 passage quotes and offsets remain
clearly attributed to the extractor source reference.

## Generate a report

From this directory, using Python 3.10 or newer:

```bash
python -m edd_report --input examples/report_input.json --output examples/example_report.md
```

Omit `--output` to print the Markdown report to standard output. The Python API
is `build_report_data(...)`, `render_markdown(report_data)`, or the convenience
function `generate_report(case_record, **options)`.

If `generated_at` is omitted, the generator records the current UTC time. Pass a
timestamp explicitly to reproduce a report exactly. `report_version` defaults
to `1.0.0`; dataset version is never guessed from the report version.

## Tests

Install the development dependency and run `python -m pytest -q`, or execute
`python tests/test_report.py`. Tests cover EDD-001/002/004/006/007 inputs,
evidence-linked findings, missing evidence, generated-only evidence, source
passage attribution, UTC timestamp handling, unresolved conflicts, and the
absence of an automatic final decision.

## Limitations

The report generator formats input; it does not authenticate sources, check
source quotes against original documents, determine whether a finding is true,
resolve contradictions, calculate risk, or replace jurisdictional and
institutional review. Upstream validation remains necessary. All bundled names,
references, claims, records, and allegations are fictional placeholders.
