# EDD Benchmark Scorecard

- Benchmark: `G4F-SW-EDD-SCORECARD-SYNTHETIC` v1.0.0
- Run ID: `SW007-EXAMPLE-RUN-001`
- System: Synthetic EDD example evaluator (1.0.0)
- Model: none / not_applicable_deterministic_rules
- Cases: 2

| Metric | Value | Numerator | Denominator | Status | Missing | Reason |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| evidence_coverage | 0.7500 | 3 | 4 | available | 0 |  |
| citation_correctness | 0.8333 | 5 | 6 | available | 0 |  |
| unsupported_claim_rate | 0.5000 | 3 | 6 | available | 0 |  |
| contradiction_detection_recall | 1.0000 | 1 | 1 | available | 0 |  |
| contradiction_detection_precision | 1.0000 | 1 | 1 | available | 0 |  |
| human_escalation_recall | 1.0000 | 1 | 1 | available | 0 |  |
| human_escalation_precision | 1.0000 | 1 | 1 | available | 0 |  |
| unnecessary_escalation_rate | 0.0000 | 0 | 1 | available | 0 |  |
| policy_violation_rate | 1.0000 | 2 | 2 | available | 0 |  |
| runtime_ms | 148.6000 | 148.6 | 1 | available | 0 |  |
| total_cost_usd | N/A | N/A | N/A | not_applicable | 0 | No model endpoint or paid API was used; this is not an estimate of local compute cost. |

## Case details

| Case | Findings | Unsupported | Evidence covered | Escalation expected / observed | Policy assessment / violations |
| --- | ---: | ---: | --- | --- | --- |
| SW007-CASE-001 | 4 | 2 | 2/2 | True / escalated | complete / P-UNSUPPORTED-CURRENT-OWNERSHIP, P-INVALID-CITATION |
| SW007-CASE-002 | 2 | 1 | 1/2 | False / not_escalated | complete / P-UNAUTHORIZED-APPROVAL |

## Aggregate

No aggregate score is calculated.
