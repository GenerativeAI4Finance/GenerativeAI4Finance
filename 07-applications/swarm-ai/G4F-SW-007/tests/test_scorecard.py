import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scorecard.metrics import SCHEMA_PATH, score_benchmark_run, validate_run


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "example_benchmark_run.json"


def load_example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def metric(report, name):
    return next(item for item in report["metrics"] if item["metric"] == name)


def test_schema_and_example_metrics_are_reproducible():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    run = load_example()
    first = score_benchmark_run(run)
    second = score_benchmark_run(run)
    assert first == second
    assert metric(first, "evidence_coverage")["value"] == 0.75
    assert metric(first, "citation_correctness")["value"] == pytest.approx(5 / 6)
    assert metric(first, "unsupported_claim_rate")["value"] == 0.5
    assert metric(first, "contradiction_detection_recall")["value"] == 1
    assert metric(first, "contradiction_detection_precision")["value"] == 1
    assert metric(first, "human_escalation_recall")["value"] == 1
    assert metric(first, "human_escalation_precision")["value"] == 1
    assert metric(first, "unnecessary_escalation_rate")["value"] == 0
    assert metric(first, "policy_violation_rate")["value"] == 1
    assert metric(first, "runtime_ms")["value"] == 148.6
    assert metric(first, "total_cost_usd")["value"] is None
    assert metric(first, "total_cost_usd")["status"] == "not_applicable"
    assert first["aggregate_score"]["status"] == "not_computed"


def test_no_findings_does_not_turn_undefined_rates_into_zero():
    run = load_example()
    for case in run["cases"]:
        case["system_output"]["findings"] = []
    report = score_benchmark_run(run, verify_hashes=False)
    assert metric(report, "evidence_coverage")["value"] == 0
    for name in ("citation_correctness", "unsupported_claim_rate"):
        result = metric(report, name)
        assert result["value"] is None
        assert result["status"] == "not_available"


def test_missing_cost_and_partial_policy_assessment_are_explicit():
    run = load_example()
    run["run_metadata"].update(cost_status="not_reported", cost_usd=None, cost_reason="Cost telemetry was unavailable.")
    run["cases"][1]["system_output"].update(policy_assessment_status="not_reported", policy_violations=[])
    report = score_benchmark_run(run, verify_hashes=False)
    cost = metric(report, "total_cost_usd")
    policy = metric(report, "policy_violation_rate")
    assert cost["value"] is None and cost["status"] == "not_available"
    assert cost["reason"] == "Cost telemetry was unavailable."
    assert policy["status"] == "partial" and policy["missing_count"] == 1
    assert policy["denominator"] == 1


def test_bad_quote_is_counted_as_incorrect_and_unsupported():
    run = load_example()
    run["cases"][0]["system_output"]["findings"][0]["citations"][0]["quote"] = "not the source text"
    report = score_benchmark_run(run, verify_hashes=False)
    assert metric(report, "citation_correctness")["value"] == pytest.approx(4 / 6)
    assert metric(report, "unsupported_claim_rate")["value"] == pytest.approx(4 / 6)


def test_hash_mismatch_is_rejected():
    run = load_example()
    run["run_metadata"]["dataset_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="dataset_sha256"):
        validate_run(run)


def test_missing_runtime_is_not_reported_as_zero():
    run = load_example()
    run["run_metadata"].update(runtime_status="not_reported", runtime_ms=None, runtime_missing_reason="Timer unavailable.")
    report = score_benchmark_run(run, verify_hashes=False)
    result = metric(report, "runtime_ms")
    assert result["value"] is None and result["status"] == "not_available"
    assert result["reason"] == "Timer unavailable."
