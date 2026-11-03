# G4F-SW-003: Multi-Agent EDD Baseline

A minimal, deterministic prototype that runs four simulated roles in a fixed
sequence: source collector, entity matcher, evidence analyst, and reviewer. It
consumes the synthetic scenario format from G4F-SW-002, requires no model API or
agent framework, and produces a source-linked report plus a full per-role
input/output trace.

## Project layout

- `edd_swarm_baseline/` — replaceable role interface, deterministic role
  implementations, fixed workflow, and command-line entry point.
- `config/workflow.json` — role order, extraction patterns, and scenario-specific
  synthetic subjects and review policies.
- `examples/example_output.json` — generated output for the conflicting and
  duplicated evidence scenario.
- `tests/test_workflow.py` — deterministic rerun, provenance, uncertainty,
  review escalation, and log checks.
- G4F-SW-002 scenario fixtures — consumed directly from the sibling task folder;
  no scenario data is copied or redefined here.

All inputs are fictional and marked synthetic. The runner never exposes a
scenario's `ground_truth` to the agent roles. The ground truth is for evaluating
the result after the run. No external service, model provider, network call,
or real operational tool is used.

## Run

From this directory with Python 3.10 or newer:

```bash
python -m edd_swarm_baseline
```

The default run uses G4F-SW-002-001 and writes
`examples/example_output.json`. To select another scenario or output path:

```bash
python -m edd_swarm_baseline --scenario G4F-SW-002-003 --output output/review_case.json
```

Available scenario IDs are listed by:

```bash
python -m edd_swarm_baseline --list-scenarios
```

Run tests:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

## Workflow and records

The execution order is configured and fixed. Each role receives only the
synthetic inputs and prior role outputs needed for its job. `trace` records the
exact JSON-compatible input and output for every role and mock tool call. A
stable run ID is derived from the scenario and configuration; timestamps and
random sampling are omitted to keep reruns byte-for-byte reproducible.

The report includes findings with `scenario_id`, `input_id`, `source_id`, exact
quoted text, and zero-based character offsets with an exclusive end. These are
references into the synthetic scenario fixture, not external citations or
G4F-EDD-002 evidence records. The report also preserves uncertainty and
unresolved issues. A human-review request is a logged mock event only.

The reviewer applies explicit rules; it does not infer truth from agent
agreement. Similar role outputs do not count as independent evidence. The
reviewer preserves contradictions, flags duplicated lineage, treats document
instructions as untrusted content, and escalates ambiguous name-only matches.

## Extension boundary and limitations

Implementations can replace individual roles through the `AgentRole` protocol,
but must preserve the role input/output contract, trace logging, and tool
allowlist. Dynamic agent coordination and provider integrations are outside
this baseline. The rule-based entity matching is deliberately limited to
configured synthetic subjects and does not establish identity. This prototype
is not an EDD decision engine, screening product, or production security
assessment.
