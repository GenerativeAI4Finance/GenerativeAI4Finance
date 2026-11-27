import json
from pathlib import Path

import pytest

from incident_scenarios import load_scenarios, run_scenario, validate_scenario
from incident_scenarios.validation import TASK_ROOT


SCHEMA = TASK_ROOT / "schema" / "incident-scenario.schema.json"
EXAMPLES = TASK_ROOT / "examples"


def test_schema_is_valid_and_all_examples_pass():
    from jsonschema import Draft202012Validator

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    scenarios = load_scenarios()
    assert len(scenarios) == 3
    for scenario in scenarios:
        validate_scenario(scenario)


def test_examples_are_local_bounded_reproducible_and_pass_toy_app():
    for scenario in load_scenarios():
        assert scenario["synthetic"] is True
        assert scenario["environment"] == {
            "execution_mode": "local_toy_app",
            "network_access": False,
            "production_access": False,
            "external_tools": False,
        }
        first = run_scenario(scenario)
        second = run_scenario(scenario)
        assert first == second
        assert first["seed"] == scenario["seed"]
        assert first["passed"] is True
        assert first["detections"] == scenario["expected_detections"]
        assert first["responses"] == scenario["safe_response"]


def test_cross_references_must_resolve():
    scenario = load_scenarios()[0]
    scenario["simulated_events"][0]["target_asset_id"] = "missing-asset"
    with pytest.raises(ValueError, match="declared asset"):
        validate_scenario(scenario)


def test_production_and_network_execution_are_rejected():
    scenario = load_scenarios()[0]
    scenario["environment"]["network_access"] = True
    with pytest.raises(ValueError, match="invalid scenario"):
        validate_scenario(scenario)


def test_duplicate_event_identifiers_are_rejected():
    scenario = load_scenarios()[0]
    scenario["simulated_events"].append(dict(scenario["simulated_events"][0]))
    with pytest.raises(ValueError, match="event_id values must be unique"):
        validate_scenario(scenario)


def test_scenario_loader_uses_json_fixtures_only():
    assert all(path.suffix == ".json" for path in EXAMPLES.iterdir())
