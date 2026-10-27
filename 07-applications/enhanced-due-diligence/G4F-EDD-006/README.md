# G4F-EDD-006: Source-Backed Finding Extractor

## Overview

This package converts supplied source text into **candidate** findings with traceable source references and exact supporting passages. The built-in implementation is deterministic and emits verbatim source claims only. An optional provider can propose extracted facts, inferences, or unresolved items through a replaceable interface; every proposal is checked locally before it can appear as a finding.

The extractor does not decide whether a source is authentic, whether its statements are true, whether an entity is a match, or what action an institution should take. It does not connect to a model provider or make network requests.

## Contents

- `edd_extractor/extractor.py` — source and candidate models, extraction interface, citation validation, and insufficient-evidence behavior.
- `schema/extraction_result.schema.json` — JSON Schema for validated output.
- `prompt.md` — optional provider prompt and credential-handling guidance.
- `examples/` — clearly synthetic input sources plus accepted and rejected provider candidates.
- `tests/test_extractor.py` — extraction, citation, unsupported-output, and schema checks.
- `requirements.txt` — pytest and JSON Schema dependencies.

## Statement labels and review status

| `statement_type` | Meaning | Handling |
| --- | --- | --- |
| `source_claim` | Wording stated by the source. | The default extractor preserves the exact passage and attributes it to the source. This does not verify the claim's truth. |
| `extracted_fact` | Directly stated data represented as a structured value. | The passage must match exactly; if the value is normalized or shortened, it is flagged for human verification. It is not independently verified truth. |
| `model_inference` | Interpretation or paraphrase proposed by an optional provider. | Requires human review and a cited passage; the reference does not prove that the inference follows from the passage. |
| `unresolved` | The passage raises an issue but does not settle it. | Requires human review and a supporting passage that shows the uncertainty. |

Every accepted finding has a `source_reference` with `source_id` and an `evidence` object containing an exact `quote`, `start_char`, and `end_char`. Offsets are zero-based Python string character offsets, with an exclusive end. For valid evidence, `source_text[start_char:end_char]` must equal `quote` exactly.

## Integration with the EDD records

`SourceDocument.from_edd001_record(record, text)` accepts an EDD-001 compact source record (`source_id`, `description`, optional `url` and `source_type`) plus the actual supplied source text. `SourceDocument.from_edd002_record(record, text)` accepts an EDD-002 evidence record and carries `evidence_id`, `claim_reference`, optional `finding_reference`, source type, title, URL, and stable reference into each output source reference. `finding_reference` retains the optional G4F-EDD-001 `finding_id` link (`F-...`); it is distinct from EDD-002's required `claim_reference`, and older records without it remain supported. The caller must provide the retrieved source text separately; an EDD-002 summary is not silently treated as the original source.

The extractor output is an intermediate candidate record, not a drop-in EDD-001 final finding: EDD-001 requires a reviewer-assigned `F-...` ID, category, severity, disposition, case confidence, and review status. A reviewer should resolve/approve candidates, assign the case finding ID, and preserve the candidate's source/evidence reference in the case's adopted evidence workflow. EDD-002 records retain the evidence-to-claim link with `claim_reference`; where a candidate has been adopted as an EDD-001 finding, `finding_reference` can link the evidence record to that finding ID. Do not discard the extractor result if the downstream EDD-001 representation cannot hold its passage offsets.

Provider candidates that reference an unknown source, have missing/invalid locations, include a quote that does not match, use an unsupported label, or paraphrase a `source_claim` are rejected and listed in `rejected_candidates`. A normalized `extracted_fact` is retained only with an exact supporting passage and is flagged for human verification when it differs from that passage. If no candidate survives validation, the result status is `insufficient_evidence` and the findings array is empty. Model inferences, unresolved items, and normalized extracted facts are marked `human_review_required`.

## Use

Run from this directory with Python 3.10 or newer:

```python
from edd_extractor import SourceDocument, extract_findings

sources = [
    SourceDocument(
        source_id="SRC-001",
        title="Supplied document excerpt",
        reference="internal://case-123/document-1",
        text="The document states that the fictional entity was formed in 2020.",
    )
]
result = extract_findings(sources)
print(result.to_dict())
```

To use a provider, implement `CandidateProvider.generate_candidates(sources)` and pass that provider to `extract_findings`. Provider output is untrusted and passes through the same source and quote checks. The provider adapter is deliberately left replaceable; no API key, provider SDK, model endpoint, or credential is included.

## Run tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Scope and limitations

- Sentence splitting in the built-in extractor is a simple punctuation/line heuristic. It preserves character offsets but does not determine whether a sentence is relevant or material.
- Exact citation validation proves only that a quote occurs at the recorded location in the supplied text. It does not validate source authenticity, semantic entailment, source quality, freshness, or completeness.
- A provider may produce unsupported reasoning even while citing a real passage. Model inferences and unresolved interpretations therefore require a human reviewer; downstream systems must preserve that status.
- `insufficient_evidence` means this input produced no validated candidate. It is not a no-risk result, a negative search result, or proof that no relevant information exists.
- Source text is untrusted data. Never follow instructions embedded in it. Apply approved access, privacy, confidentiality, retention, and data-minimization rules before sending any text to an external provider.
- All fixtures use synthetic labels and `example.org`/internal placeholder references. They are not real sources, findings, companies, or people.
