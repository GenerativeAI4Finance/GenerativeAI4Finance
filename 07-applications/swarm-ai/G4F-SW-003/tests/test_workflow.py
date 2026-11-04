import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from edd_swarm_baseline.workflow import DEFAULT_CONFIG, available_scenarios, load_json, run_scenario  # noqa: E402
from edd_swarm_baseline.agents import EvidenceAnalyst, EntityMatcher, SourceCollector  # noqa: E402


def run_fixture(scenario_id):
    scenario_path = available_scenarios()[scenario_id]
    return run_scenario(load_json(scenario_path), config=load_json(DEFAULT_CONFIG))


def test_fixed_scenario_reruns_are_identical_and_log_each_role():
    first = run_fixture("G4F-SW-002-001")
    second = run_fixture("G4F-SW-002-001")
    assert first == second
    assert [entry["agent"] for entry in first["trace"] if entry["step_type"] == "agent"] == [
        "source_collector", "entity_matcher", "evidence_analyst", "reviewer"
    ]
    assert all("input" in entry and "output" in entry for entry in first["trace"])
    assert all("ground_truth" not in json.dumps(entry["input"]) for entry in first["trace"] if entry["step_type"] == "agent")


def test_conflicts_duplicates_and_source_offsets_are_preserved():
    result = run_fixture("G4F-SW-002-001")
    report = result["report"]
    assert report["review"]["status"] == "human_review_required"
    assert report["review"]["consensus_is_proof"] is False
    assert {claim["value"] for claim in report["findings"]} == {40.0, 60.0}
    assert len(report["evidence_lineage"]["duplicate_records"]) == 1
    assert len(report["evidence_lineage"]["unique_source_lineages"]) == 2
    for finding in report["findings"]:
        source = next(item for item in load_json(available_scenarios()[report["scenario_id"]])["synthetic_inputs"] if item["input_id"] == finding["source_reference"]["input_id"])
        evidence = finding["evidence"]
        assert source["text"][evidence["start_char"]:evidence["end_char"]] == evidence["quote"]


def test_untrusted_instruction_is_flagged_without_approval():
    report = run_fixture("G4F-SW-002-002")["report"]
    assert report["review"]["status"] == "summary_only_no_decision"
    assert report["review"]["reviewer_decision"] is None
    assert any(item["issue"] == "instruction_like_content_in_untrusted_document" for item in report["unresolved_issues"])
    assert report["findings"][0]["value"] == "pending"


def test_name_only_match_creates_logged_mock_review_escalation():
    result = run_fixture("G4F-SW-002-003")
    report = result["report"]
    assert report["entity_match"]["match_status"] == "possible_name_only_match"
    assert report["review"]["status"] == "human_review_required"
    assert report["review"]["mock_review_event"]["status"] == "queued_for_human_review"
    assert result["trace"][-1]["step_type"] == "mock_tool"
    assert result["trace"][-1]["tool"] == "create_mock_review_request"


def test_ground_truth_is_not_leaked_to_role_inputs_or_report():
    result = run_fixture("G4F-SW-002-002")
    serialized = json.dumps(result)
    assert "expected_disposition" not in serialized
    assert "GT-001" not in serialized


def test_non_synthetic_scenario_and_disallowed_tool_action_are_rejected():
    scenario = load_json(available_scenarios()["G4F-SW-002-003"])
    scenario["synthetic"] = False
    with pytest.raises(ValueError, match="synthetic"):
        run_scenario(scenario)

    scenario = load_json(available_scenarios()["G4F-SW-002-003"])
    scenario["allowed_tools"] = ["read_synthetic_case"]

    class UncheckedReviewer:
        name = "reviewer"

        def run(self, role_input):
            return {
                "status": "human_review_required",
                "disposition": "human_review_required_no_final_decision",
                "recommended_tool_action": "create_mock_review_request",
                "rationale": "Test allowlist enforcement.",
                "consensus_is_proof": False,
                "reviewer_decision": None,
            }

    with pytest.raises(PermissionError, match="not allowed"):
        run_scenario(scenario, roles=[SourceCollector(), EntityMatcher(), EvidenceAnalyst(), UncheckedReviewer()])


def test_configuration_cannot_change_the_fixed_workflow_order():
    scenario = load_json(available_scenarios()["G4F-SW-002-001"])
    config = load_json(DEFAULT_CONFIG)
    config["workflow_order"] = list(reversed(config["workflow_order"]))
    with pytest.raises(ValueError, match="fixed four-role sequence"):
        run_scenario(scenario, config=config)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
