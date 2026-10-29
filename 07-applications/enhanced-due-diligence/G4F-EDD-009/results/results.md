# G4F-EDD-009 Evaluation Results

- Evaluation version: 1.0.0
- Gold-set version: 1.0.0
- Dataset version: 1.0.0
- Data: synthetic

| System | Precision | Recall | Citation correctness | Unsupported-claim rate | Negative abstention | False abstention | Abstention precision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EDD-006 rule baseline | 0.500 | 1.000 | 1.000 | 0.500 | 0.333 | 0.000 | 1.000 |
| synthetic mock example (not a model run) | 0.333 | 0.333 | 1.000 | 0.667 | 0.667 | 0.333 | 0.667 |

## Additional counts

- **EDD-006 rule baseline:** 3 matched claims; 3 extra claims; 0 missed gold claims; 6/6 citations structurally correct; 1/3 negative documents abstained.
- **synthetic mock example (not a model run):** 1 matched claim; 2 extra claims; 2 missed gold claims; 3/3 citations structurally correct; 2/3 negative documents abstained.

## Limitations

- This small synthetic set is an engineering smoke test, not a representative sample or production-readiness evaluation.
- Exact-string matching does not measure semantic equivalence; paraphrases are not credited as extracted claims.
- A correct quote and offset do not prove that a claim is entailed by the passage.
- The optional bundled mock predictions are illustrative and are not outputs from an actual language model.
