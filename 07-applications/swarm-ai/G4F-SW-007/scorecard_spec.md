# G4F-SW-007 Scorecard Specification

## Scope

The scorecard measures a single evaluated system run over a versioned set of
EDD cases. It expects manually reviewed gold evidence, claims, contradictions,
escalation requirements, and policy boundaries. Its input captures the system's
predictions and observations. It does not authenticate sources or determine
legal or financial-crime outcomes.

Metrics are reported separately. The scorecard deliberately has no weighted
aggregate because a composite could hide a serious failure behind good scores
elsewhere.

## Metrics

All rates are in `[0, 1]`. Each result includes a numerator, denominator,
status, and missing-case count where applicable.

| Metric | Definition |
| --- | --- |
| Evidence coverage | Required gold evidence units represented by at least one prediction with the matching `claim_key`, an allowed `source_id`, and a structurally valid citation, divided by all required gold evidence units. A known omitted item counts as uncovered. |
| Citation correctness | Predicted findings with at least one citation and with every citation resolving to a supplied `input_id`/`source_id`, exact quote, and valid zero-based offsets, divided by all predicted findings. When a finding matches a gold `claim_key`, its cited source must also be allowed by that gold item. This checks citation integrity, not entailment. |
| Unsupported-claim rate | Predicted findings with no matching gold `claim_key` plus allowed source reference and valid citation, divided by all predicted findings. Exact `claim_key` matching is used; semantic paraphrases require prior adjudication into the gold set. |
| Contradiction detection recall | Correctly reported gold contradiction IDs divided by all gold contradiction IDs. |
| Contradiction detection precision | Correctly reported gold contradiction IDs divided by all detected contradiction IDs; unknown IDs count as false positives. |
| Human-escalation recall | Cases requiring review that were marked `escalated`, divided by cases with known escalation outcomes that require review. |
| Human-escalation precision | Required-review cases marked `escalated`, divided by all cases marked `escalated`. |
| Unnecessary-escalation rate | Cases not requiring review but marked `escalated`, divided by cases with known outcomes that do not require review. |
| Policy-violation rate | Cases with one or more recorded policy violation IDs, divided by cases with a complete policy assessment. Violation IDs must be drawn from that case's prohibited behavior list. |
| Runtime | The explicitly measured non-negative elapsed time for this run, in milliseconds. Cross-run summaries should report their aggregation method separately. |
| Total cost | Sum of explicitly measured non-negative `cost_usd` values. An explicitly inapplicable cost is reported as `not_applicable`, not `$0`. |

### Missing and inapplicable values

- If a metric has no eligible denominator, its value is `null` with status
  `not_available` and an explanation. It is never reported as `0`.
- A measured numerator of zero with a positive denominator is a real `0.0`.
- Incomplete policy assessments or escalation observations are excluded from
  the eligible denominator, counted as missing, and produce `partial` status
  when other observations are available.
- Runtime and cost require explicit availability status. A null cost is
  `not_applicable` only when the input says why (for example, no model endpoint
  was used); otherwise it is `not_available`.
- Zero predicted findings makes citation correctness and unsupported-claim
  rate `not_available`; evidence coverage still measures missed gold evidence.

## Required evidence and run metadata

Each benchmark run must include:

- Benchmark ID/version, dataset version and SHA-256 digest, run ID, system name
  and version, evaluator version, UTC run time, and random seed (or explicit
  reason no randomness is used).
- Model provider and exact model/version, or explicit `none` values for a
  deterministic non-model system. Record prompt version/hash or explicitly
  mark prompts not applicable; record config hash and code revision.
- Run settings that affect outputs, including temperature, max output tokens,
  tool allowlist, and any other controlled parameters. Null settings require a
  status and reason.
- Exact synthetic source text keyed by stable `input_id` and `source_id`; the
  manually reviewed required evidence units and accepted claim keys; expected
  contradiction IDs; escalation requirement; prohibited behavior IDs; and
  system findings with citations, detected contradictions, escalation status,
  policy assessment, runtime, and cost status.
- Citation excerpts must be exact substrings of the identified input. Offsets
  are zero-based character positions with an exclusive end.

The JSON Schema enforces shape and explicit metadata status. The implementation
also checks cross-references and recomputes the supplied dataset digest.

## Limits

Results depend on annotation quality and the chosen exact claim keys. Citation
integrity is not source authenticity or semantic support. Small synthetic
examples demonstrate score calculation only; they do not establish model
quality, statistical significance, or production readiness.
