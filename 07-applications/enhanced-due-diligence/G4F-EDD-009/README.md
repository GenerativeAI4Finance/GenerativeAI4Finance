# G4F-EDD-009: Evaluate EDD Extraction Quality

This package evaluates EDD-006 extraction candidates against a small,
manually reviewed synthetic gold set. It runs the built-in EDD-006 rule-based
extractor as a baseline and can score optional EDD-006-shaped predictions from
a model or another candidate system. The bundled mock comparison is explicitly
labelled as illustrative; it is not an actual model run.

## Contents

- `examples/gold_set_v1.json` — versioned synthetic documents and gold claims,
  including negative and empty-document cases.
- `schema/gold_set.schema.json` — JSON Schema for the annotation format.
- `examples/mock_model_predictions.json` — synthetic mock output for testing
  the optional comparison path; not produced by a model.
- `edd_evaluation/evaluate.py` — baseline runner, metrics, and results renderer.
- `results/results.json` and `results/results.md` — reproducible comparison.
- `tests/test_evaluate.py` — gold-set, metric, citation, abstention, and EDD-006
  compatibility tests.

## Gold-set format and annotation

Each document has a stable `document_id`, `scenario`, and `source` object
compatible with EDD-006 `SourceDocument` input (`source_id`, title, reference,
source type, and exact source text). `gold_findings` contains manually reviewed
claims with `gold_id`, exact statement text, `statement_type`, supporting quote,
zero-based character offsets with an exclusive end, and an annotation note.
An empty `gold_findings` array explicitly marks a negative case; it does not
mean the source record is missing.

All names, documents, claims, and references in the gold set are fictional.
Reviewers should verify every quote and offset, label subject-specific claims,
and leave boilerplate, empty fields, and no-subject text unannotated. For a
maintained gold set, use independent annotation and record adjudication notes;
the included sample is a small illustrative fixture, not independently
double-annotated ground truth.

## Metrics and matching rules

Claims match one-to-one by `source_id`, whitespace-collapsed and case-folded
exact statement text, and exact `statement_type`. This conservative rule is
fully reproducible but does not credit semantic paraphrases.

| Metric | Definition |
| --- | --- |
| Extraction precision | Matched predicted claims / all predictions |
| Extraction recall | Matched predicted claims / all gold claims |
| Extraction F1 | Harmonic mean of extraction precision and recall |
| Citation correctness | Predictions whose source ID identifies the evaluated document and whose quote exactly equals `source_text[start_char:end_char]` / all predictions |
| Unsupported-claim rate | Predictions that do not match a gold claim **or** have an incorrect citation / all predictions |
| Negative-case abstention rate | Negative documents with zero predictions / all negative documents |
| Positive-case false-abstention rate | Positive documents with zero predictions / all positive documents |
| Abstention precision | Negative documents with zero predictions / all documents with zero predictions |

All ratios are in `[0, 1]`, rounded to six decimals in JSON and three decimals
in the Markdown table. A zero denominator yields `0.0`. Citation correctness is
structural: a matching quotation does not establish that the passage entails a
claim. Unsupported-claim rate deliberately counts incorrect citations as
unsupported, even if claim text matches. The raw counts and per-document results
are retained alongside the ratios.

## Run

From this directory, with Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m edd_evaluation
```

This runs the rule baseline and the bundled mock example, then rewrites the
results under `results/`. Run the baseline alone with:

```bash
python -m edd_evaluation --baseline-only
```

To compare a model or another system, provide a JSON wrapper with a
`system_name` and `predictions_by_document`. Each candidate uses EDD-006's
validated finding shape (`statement`, `statement_type`, `source_reference`,
`evidence` with exact quote and offsets, and review status). Omitted documents
are treated as abstentions; unknown document IDs are rejected. No provider,
network connection, or credentials are required by this evaluator.

To select explicit files or output paths, use `--gold-set`,
`--model-predictions`, `--json-output`, and `--markdown-output`.

## Results and limitations

The committed result table compares the deterministic EDD-006 rule baseline
with the bundled synthetic mock output. It is there to exercise the comparison
workflow and is not evidence that a model performs better or worse. The small
sample intentionally includes irrelevant boilerplate, a blank-field negative,
and an empty document. The baseline's sentence splitter emits boilerplate as
verbatim candidates, which the negative cases count as false positives.

These metrics are a smoke test for citation handling and evaluation logic, not
a production-readiness assessment. The sample is tiny and synthetic, gold labels
cover only exact source claims, and the strict matching rule undercounts valid
paraphrases while failing to measure semantic entailment. Citation correctness
checks offsets against supplied text only. No population-level confidence
intervals or claims about real persons, entities, jurisdictional outcomes, or
financial-crime detection are supported.
