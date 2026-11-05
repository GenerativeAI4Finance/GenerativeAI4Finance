# G4F-SW-005: Coordination Failure and Correlated Error Evaluation

This experiment compares a source-faithful single-agent rule baseline with a
three-agent configuration on the same two synthetic EDD cases from G4F-SW-002:
conflicting/duplicated ownership evidence and an untrusted document
instruction. Both configurations receive identical source inputs. Gold labels
are held back from simulated agents and used only by the evaluator.

The multi-agent configuration uses a deterministic, explicitly documented
fault-injection rule: every simulated analyst applies the same unsafe
assumption (newest ownership statement wins, or an embedded document
instruction establishes approval). This tests repeated correlated errors and
majority aggregation. It is not an LLM or independent-model benchmark.

## Contents

- `config/experiment.json` — case IDs, seeds, agent counts, implementation and
  model version metadata, and aggregation strategy.
- `experiment_runner/` — experiment execution, scoring, result rendering, and
  CLI.
- `results/results.json` and `results/results.md` — generated metrics, case
  outputs, failures, run settings, latency, and cost availability.
- `tests/test_experiment.py` — same-case, scoring, correlation, isolation, and
  reproducibility checks.

## Run

From this directory with Python 3.10 or newer:

```bash
python -m pytest -q
python -m experiment_runner
```

The runner writes results under `results/`. It imports the fictional scenario
records from the sibling `G4F-SW-002` directory. No external systems, provider
endpoints, network, or tools are used.

## Metric definitions

| Metric | Definition |
| --- | --- |
| Unsupported claim count/rate | Emitted claims not matching a ground-truth predicate, value, and cited source ID; rate divides by all emitted claims. |
| Missed evidence count | Ground-truth facts with no matching emitted claim. |
| Duplicate work | Agent-source review assignments beyond one review per unique source record (`assignments - unique sources`). |
| Contradiction handling | Pass when all conflicting source claims are preserved and no winning value is silently selected. Not applicable when the case has no contradiction. |
| Correlated error | An identical unsupported assumption emitted by at least two separate agents for the same case. This is a count of simulated repeated errors, not a statistical correlation coefficient. |
| Latency | Observed local elapsed wall time for each full system run, in milliseconds. It varies by machine and run. |
| Cost | External API cost is `null` because no model endpoint is called. This is not an estimate of compute or engineering cost. |

Results report failures as observed. The sample has only two cases, so it does
not support population-level rates, confidence intervals, model rankings, or
production-readiness claims.
