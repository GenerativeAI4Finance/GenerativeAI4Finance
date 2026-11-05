import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SCHEMA_PATH = ROOT / "schema" / "scenario.schema.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def schema():
    result = read_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(result)
    return result


def scenarios():
    return [read_json(path) for path in sorted(EXAMPLES.glob("*.json"))]


def test_all_three_scenarios_validate_and_have_expected_outcomes(schema):
    loaded = scenarios()
    assert len(loaded) == 3
    validator = Draft202012Validator(schema)
    for scenario in loaded:
        validator.validate(scenario)
        assert scenario["synthetic"] is True
        assert scenario["determinism"]["deterministic_inputs"] is True
        assert scenario["ground_truth"]["expected_disposition"]
        assert scenario["expected_safe_behavior"]
        assert scenario["prohibited_actions"]
        assert scenario["evaluation_metrics"]


def test_scenario_and_input_ids_are_unique_and_references_resolve(schema):
    loaded = scenarios()
    scenario_ids = [item["scenario_id"] for item in loaded]
    assert len(scenario_ids) == len(set(scenario_ids))

    for scenario in loaded:
        inputs = scenario["synthetic_inputs"]
        input_ids = [item["input_id"] for item in inputs]
        assert len(input_ids) == len(set(input_ids))
        source_ids = {item["source_id"] for item in inputs if item["source_id"] is not None}
        for item in inputs:
            if item["duplicate_of"] is not None:
                assert item["duplicate_of"] in source_ids
        for fact in scenario["ground_truth"]["facts"]:
            assert set(fact["source_ids"]) <= source_ids


def test_requested_scenario_types_are_present():
    loaded = scenarios()
    combined = " ".join(
        [scenario["title"] + " " + scenario["objective"] for scenario in loaded]
        + [text for scenario in loaded for text in scenario["expected_safe_behavior"]]
    ).casefold()
    assert "contradict" in combined
    assert "duplicat" in combined
    assert "untrusted" in combined
    assert "human" in combined and "review" in combined


def test_schema_rejects_non_synthetic_or_missing_expected_behavior(schema):
    validator = Draft202012Validator(schema)
    scenario = scenarios()[0]

    non_synthetic = {**scenario, "synthetic": False}
    assert list(validator.iter_errors(non_synthetic))

    missing_expectations = {key: value for key, value in scenario.items() if key != "expected_safe_behavior"}
    assert list(validator.iter_errors(missing_expectations))


def test_duplicate_evidence_case_preserves_conflict_and_lineage():
    scenario = next(item for item in scenarios() if item["scenario_id"] == "G4F-SW-002-001")
    claims = [fact for fact in scenario["ground_truth"]["facts"] if fact["predicate"] == "ownership_percent_claim"]
    assert {claim["value"] for claim in claims} == {40, 60}
    duplicate = next(item for item in scenario["synthetic_inputs"] if item["duplicate_of"] is not None)
    assert duplicate["duplicate_of"] == "SRC-001"
    assert scenario["ground_truth"]["expected_disposition"] == "conflict_preserved_human_review_required"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
