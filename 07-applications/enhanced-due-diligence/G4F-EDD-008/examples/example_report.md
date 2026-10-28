# EDD Review Report — G4F-EDD-801

> This report organizes supplied review data. It does not make a final risk, compliance, onboarding, or enforcement decision.

## Report metadata

- Report version: 1.0.0
- Dataset version: 1.0.0
- Generated at (UTC): 2026-10-28T12:00:00Z
- Synthetic dataset: Yes

## Scope

Illustrative review of synthetic ownership records for the fictional Example Orchard Trading Ltd.

## Subject summary

- Subject type: company
- Subject name: Example Orchard Trading Ltd.
- Subject ID: SYN-ENTITY-801
- Jurisdiction: GB
- Review date: 2026-10-28
- Case review status (from input): in\_review
- Risk categories recorded in case file: \['ownership\_opacity'\]
- Case confidence (input value; not recalculated): 0.4

## Findings

### F-801 — ownership\_opacity

- Summary from case record: The supplied records state different ownership percentages and require reconciliation.
- Severity from case record: medium
- Disposition from case record: unresolved
- Evidence note: Case-record summary is reproduced as supplied and is not an independent verification.
- Linked evidence:
  - **EDD-EV-801** — Synthetic ownership register excerpt A; type: official\_record; status: available; checked/accessed: 2026-10-27; URL/reference: https://example.org/synthetic/record-a; classification: \['primary'\]
  - **EDD-EV-802** — Synthetic shareholder statement B; type: user\_document; status: disputed; checked/accessed: 2026-10-27; URL/reference: https://example.org/synthetic/record-b; classification: \['user\_provided'\]
    - Source-record excerpt/summary (as recorded): SYNTHETIC SOURCE SUMMARY: Record A lists a 60 percent holding.
    - Source-record excerpt/summary (as recorded): SYNTHETIC SOURCE SUMMARY: Statement B lists a 40 percent holding.
- Model-generated/inferred candidate (model\_inference; requires\_human\_review): The difference may result from a recent ownership transfer.
  - Source reference: {'source\_id': 'SRC-801', 'evidence\_id': 'EDD-EV-801', 'claim\_reference': 'CLAIM-801', 'finding\_reference': 'F-801', 'title': 'Synthetic ownership excerpt A', 'reference': 'SYN-REG-A-801'}
  - Supporting source passage: SYNTHETIC SOURCE: Record A lists 60 percent; Record B lists 40 percent.
  - Passage offsets: 0–71

## Findings without an evidence link

These case finding summaries are withheld because qualifying source evidence was not available:
- F-802 (adverse\_media): Only unavailable/generated evidence or a non-source-claim candidate is linked; summary withheld pending source support.

## Extractor outputs not adopted as case findings

These are candidate outputs, not approved case findings:
- **Source-claim candidate** (CAND-0802; type: source\_claim; review: source\_backed\_candidate): A source sentence without a case finding link.
  - Source: {'source\_id': 'SRC-999', 'title': 'Synthetic separate source', 'reference': None}
  - Exact cited passage: SYNTHETIC SOURCE: Separate example sentence.
  - Passage offsets: 0–44

## Source references

- **EDD-EV-801** — Synthetic ownership register excerpt A; type: official\_record; status: available; checked/accessed: 2026-10-27; URL/reference: https://example.org/synthetic/record-a; classification: \['primary'\]
  - Excerpt/summary (as recorded): SYNTHETIC SOURCE SUMMARY: Record A lists a 60 percent holding.
  - Provenance: Fictional test record; example.org URL is a placeholder.
- **EDD-EV-802** — Synthetic shareholder statement B; type: user\_document; status: disputed; checked/accessed: 2026-10-27; URL/reference: https://example.org/synthetic/record-b; classification: \['user\_provided'\]
  - Excerpt/summary (as recorded): SYNTHETIC SOURCE SUMMARY: Statement B lists a 40 percent holding.
  - Provenance: Fictional user-provided document fixture.
- **EDD-EV-803** — Generated synthetic note; type: other; status: available; checked/accessed: 2026-10-27; URL/reference: SYN-GEN-803; classification: \['generated'\]
  - Excerpt/summary (as recorded): Generated placeholder; not independent evidence.
  - Provenance: Synthetic fixture illustrating generated material.
- **SRC-801** — Synthetic registry excerpt A; type: registry; status: Not provided; checked/accessed: 2026-10-27; URL/reference: https://example.org/synthetic/record-a
- **SRC-802** — Synthetic shareholder statement B; type: other; status: Not provided; checked/accessed: 2026-10-27; URL/reference: https://example.org/synthetic/record-b

## Contradiction and freshness checks

- **Unresolved conflict** for SYNTHETIC-COMPANY-801, attribute ownership\_percentage; resolution: `unresolved_requires_human_review`.
  - Value: 6E+1
    - Observation OBS-801-A: 60; source reference: {'evidence\_id': 'EDD-EV-801'}
  - Value: 4E+1
    - Observation OBS-801-B: 40; source reference: {'evidence\_id': 'EDD-EV-802'}

## Unresolved questions

- Which ownership document reflects the current registered position?
- Does a source passage directly support case finding F-802?
- Resolve the conflicting ownership\_percentage observations for SYNTHETIC-COMPANY-801.
- Review evidence record EDD-EV-802 marked disputed.

## Limitations

- This example report contains synthetic, placeholder content only.
- Extractor quotes and offsets are reproduced from EDD-006 output; this report does not revalidate them against the original source text.
- EDD-EV-801: Synthetic only; no real registry was consulted.
- EDD-EV-802: The value conflicts with the synthetic registry excerpt.
- EDD-EV-803: Generated content cannot independently support a case finding.

## Recommended review actions

- Obtain a current ownership record and reconcile it with the shareholder statement.
- Substantiate case finding F-802 using reviewable source evidence; model output alone is not sufficient.
- Human-review the conflicting ownership\_percentage observations; preserve all sources until resolved.
- Resolve or qualify evidence record EDD-EV-802 marked disputed.

## Decision boundary

No overall accusation, risk rating, or automatic final decision is generated by this report.
