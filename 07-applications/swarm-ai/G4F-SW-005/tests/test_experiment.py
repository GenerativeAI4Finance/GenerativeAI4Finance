import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment_runner.runner import DEFAULT_CONFIG, load_json, run_experiment  # noqa: E402


def test_same_synthetic_cases_and_versions_are_recorded_for_all_systems():
    result = run_experiment()
    case_ids = [case["case_id"] for case in result["case_manifest"]]
    assert case_ids == ["CASE-SW005-001", "CASE-SW005-002"]
    assert result["network_access"] is False
    assert result["seed"] == 5005
    for system in result["systems"]:
        assert [case["case_id"] for case in system["case_results"]] == case_ids
        assert system["implementation_version"]
        assert system["model_version"] is None


def test_single_agent_preserves_conflict_and_evidence_without_correlated_error():
    result = run_experiment()
    single = next(item for item in result["systems"] if item["system_id"] == "single_agent_baseline")
    conflict_case = single["case_results"][0]
    assert conflict_case["contradiction_handling_pass"] is True
    assert conflict_case["missed_evidence_count"] == 0
    assert conflict_case["unsupported_claims"] == 0
    assert conflict_case["correlated_error_count"] == 0


def test_multi_agent_configuration_surfaces_correlated_failure_modes():
    result = run_experiment()
    multi = next(item for item in result["systems"] if item["system_id"] == "multi_agent_fault_injection")
    conflict_case, injection_case = multi["case_results"]
    assert conflict_case["contradiction_handling_pass"] is False
    assert conflict_case["correlated_errors"][0]["agent_count"] == 3
    assert injection_case["unsupported_claims"] == 3
    assert injection_case["correlated_errors"][0]["agent_count"] == 3
    assert sum(case["duplicate_work_units"] for case in multi["case_results"]) > 0


def test_citations_are_checked_for_every_emitted_claim():
    result = run_experiment()
    for system in result["systems"]:
        for case in system["case_results"]:
            assert case["citation_correctness"] == 1.0


def test_latency_and_cost_availability_are_reported():
    result = run_experiment()
    for system in result["systems"]:
        assert system["latency_ms"] >= 0
        assert system["external_api_cost_usd"] is None
        assert system["cost_status"] == "not_applicable_no_model_endpoint"


def test_case_outcomes_and_failure_metrics_reproduce_across_runs():
    first = run_experiment()
    second = run_experiment()
    assert first["case_manifest"] == second["case_manifest"]
    for first_system, second_system in zip(first["systems"], second["systems"]):
        assert first_system["system_id"] == second_system["system_id"]
        assert first_system["case_results"] == second_system["case_results"]
        assert first_system["implementation_version"] == second_system["implementation_version"]


def test_gold_truth_is_not_sent_to_agent_outputs():
    result = run_experiment()
    for system in result["systems"]:
        for case in system["case_results"]:
            serialized_outputs = str(case["agent_outputs"])
            assert "expected_disposition" not in serialized_outputs
            assert "GT-001" not in serialized_outputs


def test_unknown_model_endpoint_is_not_silently_loaded():
    config = load_json(DEFAULT_CONFIG)
    changed = copy.deepcopy(config)
    changed["systems"][0]["model_version"] = "unconfigured-model"
    with pytest.raises(ValueError, match="local-only"):
        run_experiment(changed)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
