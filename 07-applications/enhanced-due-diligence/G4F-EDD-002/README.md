
# G4F-EDD-002: Source and Evidence Record Format

## Overview

This project defines a consistent JSON record format for documenting
sources used in Enhanced Due Diligence (EDD) reviews.

Each evidence record identifies its source, records when it was checked,
documents its provenance and limitations, and links it to a specific
claim using `claim_reference`.

All five examples are fictional test fixtures. They are not real sources,
citations, companies, findings or allegations.

## Project structure

- `schema.json`: JSON Schema Draft 2020-12.
- `examples/`: Five fictional evidence records.
- `tests/test_schema.py`: Automated validation tests.
- `requirements.txt`: Python validation dependency.

## Evidence record fields

| Field | Purpose |
|---|---|
| evidence_id | Unique evidence record identifier |
| claim_reference | Identifier of the claim associated with the evidence |
| title | Source title or descriptive placeholder |
| publisher | Publisher, author or issuing organization |
| url | Source URL, if available |
| reference | Document identifier or traceable reference |
| publication_date | Publication date, or null if unknown |
| access_date | Actual access date, or null if not accessed |
| source_type | Type of source or document |
| source_classification | Applicable source classifications |
| jurisdiction | Relevant jurisdiction, if known |
| excerpt_or_summary | Relevant excerpt or neutral summary |
| provenance_notes | Origin, handling and verification notes |
| evidence_status | Available, unavailable, disputed or outdated |
| limitations | Known gaps, uncertainties and caveats |

## Claim references

`claim_reference` identifies the claim to which an evidence record
relates. It is not the claim itself and does not establish that the
claim is true.

Example:

    {
      "evidence_id": "EDD-EV-001",
      "claim_reference": "CLAIM-001"
    }

In an actual EDD case, `CLAIM-001` should correspond to a claim recorded
in the case findings or another documented claim register.

Multiple evidence records may refer to the same claim. This allows an
analyst to compare supporting, conflicting or incomplete evidence.

The claim reference format in this implementation is `CLAIM-` followed
by at least three digits.

## Source classification

The schema supports the following classifications:

- `primary`: Original or direct source material.
- `secondary`: Material reporting on or interpreting other sources.
- `user_provided`: Material supplied by a user.
- `generated`: Material produced by a tool or automated process.

Classifications may overlap. For example, an official document supplied
by a user can be both `primary` and `user_provided`.

User-provided material is not automatically authentic. Generated
material must not be represented as an independently verified source.

## Evidence status

- `available`: The source has been obtained or accessed.
- `unavailable`: The source could not be obtained or inspected.
- `disputed`: Relevant information is contested or conflicting.
- `outdated`: The information may no longer reflect the current position.

These statuses describe the evidence record, not the truth of a claim.

### Unavailable evidence

Use null for unknown dates, publisher information or URLs where
permitted by the schema.

Explain why the source is unavailable in `limitations` and
`provenance_notes`. Do not invent its contents or claim that it was
accessed when it was not.

### Disputed evidence

Describe the disagreement and identify the relevant source records.
Keep conflicting claims distinguishable until the discrepancy is
resolved or appropriately qualified.

### Outdated evidence

Explain why the evidence may be stale. Record the actual access date
and seek a current source when appropriate.

An old source is not necessarily incorrect, but its relevance may
depend on the claim being assessed.

## Provenance and citation integrity

For real sources, record the actual source title, publisher, URL or
document reference, publication date and access date where available.

Distinguish direct quotations from summaries or paraphrases. Document
how the source was obtained and what verification was performed.

Never fabricate a citation, URL, publication date, access date or quote.
Use clearly labelled fictional records only for demonstrations and tests.

A source's existence does not prove every claim associated with it.
Analysts must assess relevance, reliability, context and limitations.

## Validation

### Requirements

Python 3.10 or newer is recommended.

Install dependencies:

    python -m pip install -r requirements.txt

### Run tests

From the `G4F-EDD-002` directory:

    python -m unittest discover -s tests -v

The tests verify that:

- All five example records validate.
- The schema follows Draft 2020-12.
- Required fields and claim references cannot be omitted.
- Empty claim references are rejected.
- Invalid dates, URLs, statuses and classifications are rejected.
- Duplicate classifications and unknown properties are rejected.
- Unavailable, disputed and outdated evidence requires limitations.
- An unknown access date can be represented as null.

## Scope and limitations

This project defines an evidence record format. It does not authenticate
documents, independently verify sources, resolve disputes, determine
legal compliance or establish the truth of claims.

The schema validates record structure and selected field constraints.
Human review is still necessary to assess evidence quality and meaning.

No real personal, confidential or sensitive data should be included
in the fictional examples.
