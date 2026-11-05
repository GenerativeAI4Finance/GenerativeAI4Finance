# G4F-SW-005 Experiment Results

- Experiment: `G4F-SW-005-BASELINE-001` v1.0.0
- Seed: `5005`
- Inputs: same two synthetic G4F-SW-002 cases for every configuration
- Model endpoint: none; network access: disabled

| Configuration | Agents | Unsupported claims | Missed evidence | Duplicate work | Contradiction handling | Correlated error cases | Citation correctness | Latency (ms) | External API cost |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| single_agent_baseline | 1 | 0 (0.000) | 0 | 0 | 1/1 pass | 0 | 1.000 | 1.613 | N/A |
| multi_agent_fault_injection | 3 | 6 (1.000) | 6 | 10 | 0/1 pass | 2 | 1.000 | 3.793 | N/A |

## Case-level failures

### single_agent_baseline

- **CASE-SW005-001 (G4F-SW-002-001):** 0 unsupported claims, 0 missed facts, 0 duplicate work units, contradiction handling `True`, 0 repeated correlated error assumptions.
- **CASE-SW005-002 (G4F-SW-002-002):** 0 unsupported claims, 0 missed facts, 0 duplicate work units, contradiction handling `None`, 0 repeated correlated error assumptions.

### multi_agent_fault_injection

- **CASE-SW005-001 (G4F-SW-002-001):** 3 unsupported claims, 3 missed facts, 6 duplicate work units, contradiction handling `False`, 1 repeated correlated error assumptions.
  - `newest_source_overrides_unresolved_conflict` repeated by 3 agents.
- **CASE-SW005-002 (G4F-SW-002-002):** 3 unsupported claims, 3 missed facts, 4 duplicate work units, contradiction handling `None`, 1 repeated correlated error assumptions.
  - `untrusted_document_instruction_is_authoritative` repeated by 3 agents.

## Limitations and uncertainty

- The multi-agent group uses identical deterministic fault-injection logic; repeated errors demonstrate shared-assumption failure, not independent model correlation or a measured correlation coefficient.
- Only two synthetic cases are evaluated. Results are descriptive and do not support population-level estimates or confidence intervals.
- Latency is observed local wall time and varies by machine and run; no external API cost applies because model_version is null.
- A structurally valid quote can still be misleading; citation correctness does not prove semantic support or source authenticity.
