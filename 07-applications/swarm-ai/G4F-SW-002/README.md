# G4F-SW-002: EDD Swarm Simulation Scenario Format

This package defines a versioned JSON format for deterministic, fictional EDD
swarm simulations. Each scenario records its objective, agent roles, allowed
tools, synthetic inputs, expected safe behavior, prohibited actions, ground
truth, and measurable pass conditions before a run begins.

## Contents

- `schema/scenario.schema.json` — JSON Schema Draft 2020-12 definition.
- `examples/` — three scenarios covering contradictory and duplicated evidence,
  untrusted document instructions, and escalation to a human reviewer.
- `tests/test_scenarios.py` — schema and cross-reference checks, including
  checks that scenarios are synthetic and define expected outcomes in advance.
- `requirements.txt` — test and schema-validation dependencies.

## Format decisions

Scenarios use JSON so Python's standard library can load the fixtures and the
same files can be validated directly against JSON Schema. Every scenario has
`synthetic: true`, a fixed seed, explicit initial state, and expected results
that do not depend on an LLM-generated ground truth. `allowed_tools` names the
only tools a simulated agent may use. Inputs are inert text and records; no
external service or live action is required.

The ground truth describes facts known by the scenario author and expected
disposition. It is evaluation data and should not be included in an agent's
runtime prompt unless the experiment explicitly tests leakage. The examples
contain fictional names and `example.org` references.

## Validate

From this directory, with Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Schema validation catches structural errors. Tests also check unique scenario
and input identifiers, allowed-tool references, and source lineage such as
duplicate evidence references. An evaluation runner can load a scenario,
provide only its `synthetic_inputs` and permitted tool stubs to agents, then
compare the trace and outcome with `expected_safe_behavior`,
`prohibited_actions`, `ground_truth`, and `evaluation_metrics`.

## Limits

These are test specifications, not executable agents or a claim that a system
is secure. A passing sample does not establish production readiness. Add
reviewed cases for the relevant workflow, model, tools, and institutional
policy before drawing operational conclusions.
