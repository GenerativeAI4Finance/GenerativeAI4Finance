# G4F-CYBER-002: Controlled incident scenario schema

## Purpose

This package defines a versioned JSON schema and three synthetic security scenarios for a deterministic local toy application. Scenarios cover untrusted content, unauthorized identity access, and bounded request-rate pressure. The toy app records simulated detections and safe responses; it does not connect to a model, production system, external tool, or network.

## Files

- `schema/incident-scenario.schema.json` — JSON Schema Draft 2020-12.
- `examples/` — three validated, fixed-seed scenarios.
- `incident_scenarios/validation.py` — schema, uniqueness, and cross-reference validation.
- `incident_scenarios/toy_app.py` — deterministic allowlisted event simulation.
- `tests/test_scenarios.py` — schema, behavior, reproducibility, and safety-boundary tests.
- `requirements.txt` — JSON Schema validator and pytest.

## Scenario contract

Every scenario specifies:

- synthetic asset identifiers and data classifications;
- allowlisted declarative simulated event types and bounded parameters;
- expected detection IDs linked to event IDs;
- a safe response linked to each event;
- evidence expectations and explicit pass/fail conditions;
- severity and a fixed reproducibility seed;
- a required local-only environment: `execution_mode=local_toy_app`, `network_access=false`, `production_access=false`, and `external_tools=false`.

Severity values (`low`, `moderate`, `high`, `critical`) are illustrative scenario ratings. Interpret them using the organization's impact and escalation criteria; the schema does not assign a universal severity score.

The schema rejects unknown fields and event types. Parameter shapes and ranges are limited by event type. The Python validator additionally checks unique IDs and that assets/events/evidence references resolve. Scenario fields are data, never interpreted as code or shell commands.

## Run locally

From this directory, with Python 3.10 or newer:

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

Run the toy app against all examples:

```powershell
python -c "from incident_scenarios import load_scenarios, run_scenario; [print(run_scenario(s)) for s in load_scenarios()]"
```

The runner returns `passed=true` only when its deterministic detections and safe responses match the scenario's declared expectations. It uses only in-process Python data structures. The request-burst scenario simulates a count; it does not send requests.

## Limits

These fixtures verify a toy state machine and schema, not a real financial application or production security controls. They do not prove that a system is secure. Adapt scenarios only within an authorized isolated test environment and retain applicable incident-response, privacy, and security review requirements. The defensive themes align with the [G4F-CYBER-001 taxonomy](../G4F-CYBER-001/README.md).
