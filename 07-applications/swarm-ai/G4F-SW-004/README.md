# G4F-SW-004: Evidence Contamination and Prompt Injection Tests

Local-only test harness for checking whether the deterministic G4F-SW-003 EDD
baseline treats embedded document instructions as untrusted content, preserves
source citations, and respects the scenario tool allowlist.

## Contents

- `fixtures/contamination_cases.json` — three inert, synthetic document cases.
- `edd_swarm_security_tests/` — repeatable harness, scoring, and CLI.
- `results/results.json` and `results/results.md` — generated test results.
- `mitigations.md` — defensive controls and test interpretation.
- `tests/test_resistance.py` — assertions for instruction handling, citations,
  tool permissions, and deterministic reruns.

The harness imports G4F-SW-003 and reads the existing G4F-SW-002 fixture. Keep
all three task folders together under `07-applications/swarm-ai/`. It uses no
model endpoint, network, browser, external search, email, or live tool. The
instruction-like strings are test data only and are never executed.

## Run

From this directory with Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m edd_swarm_security_tests
python -m pytest -q
```

The CLI rewrites the JSON and Markdown results deterministically. The test
target is specifically the rule-based G4F-SW-003 baseline; results do not
establish resistance of arbitrary LLMs or production systems.

## Measurements

- **Instruction handling:** all fixtures remain summary-only, the unsafe
  approval is absent, and embedded instructions are flagged as untrusted.
- **Citation integrity:** every emitted finding points to an input in the
  fixture, and its quote and offsets exactly match the supplied document text.
- **Tool permission compliance:** every observed tool call is in the fixture's
  allowlist. Current safe cases make no tool calls.
- **Determinism:** repeated runs over identical fixture/configuration produce
  identical reports and traces.

These measures are structural checks. Citation validity does not prove that a
source is authentic or that a passage semantically supports a conclusion.
