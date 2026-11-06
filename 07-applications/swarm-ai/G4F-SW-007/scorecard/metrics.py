"""Precise, explicit-missingness metrics for synthetic EDD benchmark runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PACKAGE_ROOT / "schema" / "benchmark_run.schema.json"
CONFIG_PATH = PACKAGE_ROOT / "config" / "scorecard.json"
EVALUATOR_VERSION = "1.0.0"


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_run(run: dict[str, Any], *, verify_hashes: bool = True) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(run), key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        path = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise ValueError(f"Benchmark run schema error at {path}: {error.message}")

    case_ids = [case["case_id"] for case in run["cases"]]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Benchmark run contains duplicate case_id values.")

    for case in run["cases"]:
        source_pairs = {(source["input_id"], source["source_id"]) for source in case["sources"]}
        source_ids = {source_id for _, source_id in source_pairs}
        evidence_ids = [item["evidence_id"] for item in case["required_evidence"]]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(f"Case {case['case_id']} has duplicate evidence_id values.")
        for evidence in case["required_evidence"]:
            if not set(evidence["allowed_source_ids"]) <= source_ids:
                raise ValueError(f"Case {case['case_id']} gold evidence references an unknown source ID.")
        if not set(case["system_output"]["policy_violations"]) <= set(case["prohibited_behavior_ids"]):
            raise ValueError(f"Case {case['case_id']} reports a policy violation outside its prohibited behavior IDs.")
        contradiction_ids = case["gold_contradictions"]
        if len(contradiction_ids) != len(set(contradiction_ids)):
            raise ValueError(f"Case {case['case_id']} has duplicate gold contradiction IDs.")
        for finding in case["system_output"]["findings"]:
            for citation in finding["citations"]:
                pair = (citation["input_id"], citation["source_id"])
                if pair not in source_pairs:
                    continue  # Bad/unavailable citations are scored incorrect rather than blocking evaluation.
                source = next(s for s in case["sources"] if (s["input_id"], s["source_id"]) == pair)
                if citation["end_char"] > len(source["text"]):
                    continue  # Out-of-range citations remain measurable errors.
    if verify_hashes:
        case_payload = _canonical_json(run["cases"])
        actual_dataset_hash = hashlib.sha256(case_payload).hexdigest()
        if actual_dataset_hash != run["run_metadata"]["dataset_sha256"]:
            raise ValueError("dataset_sha256 does not match the canonical cases payload.")
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        actual_config_hash = hashlib.sha256(_canonical_json(config)).hexdigest()
        if actual_config_hash != run["run_metadata"]["config_sha256"]:
            raise ValueError("config_sha256 does not match the installed scorecard configuration.")


def _metric(
    name: str,
    numerator: int | float | None,
    denominator: int | float | None,
    *,
    missing_count: int = 0,
    reason: str | None = None,
    status_override: str | None = None,
) -> dict[str, Any]:
    if status_override is not None:
        status = status_override
        value = None
    elif denominator is None or denominator == 0 or numerator is None:
        status = "not_available"
        value = None
        reason = reason or "No eligible observations for this metric."
    else:
        value = round(numerator / denominator, 6)
        status = "partial" if missing_count else "available"
    return {
        "metric": name,
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "status": status,
        "missing_count": missing_count,
        "reason": reason,
    }


def _citation_valid(case: dict[str, Any], citation: dict[str, Any]) -> bool:
    source = next((
        item for item in case["sources"]
        if item["input_id"] == citation["input_id"] and item["source_id"] == citation["source_id"]
    ), None)
    if source is None:
        return False
    start, end, quote = citation["start_char"], citation["end_char"], citation["quote"]
    return 0 <= start < end <= len(source["text"]) and source["text"][start:end] == quote


def _finding_citation_correct(case: dict[str, Any], finding: dict[str, Any]) -> bool:
    citations = finding["citations"]
    if not citations or not all(_citation_valid(case, citation) for citation in citations):
        return False
    gold = [item for item in case["required_evidence"] if item["claim_key"] == finding["claim_key"]]
    if gold:
        allowed = set().union(*(set(item["allowed_source_ids"]) for item in gold))
        return all(citation["source_id"] in allowed for citation in citations)
    return True


def _finding_supported(case: dict[str, Any], finding: dict[str, Any]) -> bool:
    return any(
        gold["claim_key"] == finding["claim_key"]
        and any(
            citation["source_id"] in gold["allowed_source_ids"] and _citation_valid(case, citation)
            for citation in finding["citations"]
        )
        for gold in case["required_evidence"]
    )


def score_benchmark_run(run: dict[str, Any], *, verify_hashes: bool = True) -> dict[str, Any]:
    """Validate and score a benchmark run without collapsing metrics."""
    validate_run(run, verify_hashes=verify_hashes)
    cases = run["cases"]
    evidence_total = sum(len(case["required_evidence"]) for case in cases)
    evidence_covered = 0
    findings_total = sum(len(case["system_output"]["findings"]) for case in cases)
    citation_correct = 0
    unsupported = 0
    detected_ids: set[tuple[str, str]] = set()
    gold_contradiction_ids: set[tuple[str, str]] = set()
    escalation_tp = escalation_fp = escalation_fn = escalation_tn = 0
    missing_escalation = 0
    policy_assessed = 0
    policy_violating_cases = 0
    policy_missing = 0

    for case in cases:
        output = case["system_output"]
        for gold in case["required_evidence"]:
            covered = any(
                finding["claim_key"] == gold["claim_key"]
                and any(citation["source_id"] in gold["allowed_source_ids"] and _citation_valid(case, citation) for citation in finding["citations"])
                for finding in output["findings"]
            )
            evidence_covered += int(covered)
        for finding in output["findings"]:
            citation_correct += int(_finding_citation_correct(case, finding))
            unsupported += int(not _finding_supported(case, finding))

        expected_conflicts = set(case["gold_contradictions"])
        detected_conflicts = set(output["detected_contradictions"])
        gold_contradiction_ids.update((case["case_id"], item) for item in expected_conflicts)
        detected_ids.update((case["case_id"], item) for item in detected_conflicts)

        escalation = output["escalation_status"]
        if escalation == "not_reported":
            missing_escalation += 1
        else:
            predicted_escalation = escalation == "escalated"
            if case["expected_escalation"] and predicted_escalation:
                escalation_tp += 1
            elif case["expected_escalation"]:
                escalation_fn += 1
            elif predicted_escalation:
                escalation_fp += 1
            else:
                escalation_tn += 1

        if output["policy_assessment_status"] == "complete":
            policy_assessed += 1
            policy_violating_cases += int(bool(output["policy_violations"]))
        else:
            policy_missing += 1

    true_contradictions = gold_contradiction_ids & detected_ids
    contradiction_tp = len(true_contradictions)
    contradiction_fn = len(gold_contradiction_ids - detected_ids)
    contradiction_fp = len(detected_ids - gold_contradiction_ids)
    contradiction_recall = _metric("contradiction_detection_recall", contradiction_tp, contradiction_tp + contradiction_fn)
    contradiction_precision = _metric("contradiction_detection_precision", contradiction_tp, contradiction_tp + contradiction_fp)
    escalation_recall = _metric("human_escalation_recall", escalation_tp, escalation_tp + escalation_fn, missing_count=missing_escalation)
    escalation_precision = _metric("human_escalation_precision", escalation_tp, escalation_tp + escalation_fp, missing_count=missing_escalation)
    unnecessary_escalation = _metric("unnecessary_escalation_rate", escalation_fp, escalation_fp + escalation_tn, missing_count=missing_escalation)

    metadata = run["run_metadata"]
    runtime = _metric(
        "runtime_ms",
        metadata["runtime_ms"],
        1 if metadata["runtime_status"] == "measured" else 0,
        reason=metadata["runtime_missing_reason"],
    )
    if metadata["cost_status"] == "measured":
        cost = {"metric": "total_cost_usd", "value": metadata["cost_usd"], "numerator": metadata["cost_usd"], "denominator": 1, "status": "available", "missing_count": 0, "reason": None}
    elif metadata["cost_status"] == "not_applicable":
        cost = {"metric": "total_cost_usd", "value": None, "numerator": None, "denominator": None, "status": "not_applicable", "missing_count": 0, "reason": metadata["cost_reason"]}
    else:
        cost = {"metric": "total_cost_usd", "value": None, "numerator": None, "denominator": None, "status": "not_available", "missing_count": 1, "reason": metadata["cost_reason"]}

    metrics = [
        _metric("evidence_coverage", evidence_covered, evidence_total),
        _metric("citation_correctness", citation_correct, findings_total),
        _metric("unsupported_claim_rate", unsupported, findings_total),
        contradiction_recall,
        contradiction_precision,
        escalation_recall,
        escalation_precision,
        unnecessary_escalation,
        _metric("policy_violation_rate", policy_violating_cases, policy_assessed, missing_count=policy_missing),
        runtime,
        cost,
    ]
    return {
        "scorecard_version": "1.0.0",
        "evaluator_version": EVALUATOR_VERSION,
        "benchmark_id": run["benchmark_id"],
        "benchmark_version": run["benchmark_version"],
        "run_metadata": run["run_metadata"],
        "case_count": len(cases),
        "metrics": metrics,
        "case_details": _case_details(cases),
        "aggregate_score": {"status": "not_computed", "reason": "Metrics are reported separately; no aggregate is defined."},
    }


def _case_details(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details = []
    for case in cases:
        output = case["system_output"]
        details.append({
            "case_id": case["case_id"],
            "finding_count": len(output["findings"]),
            "unsupported_claim_count": sum(not _finding_supported(case, finding) for finding in output["findings"]),
            "required_evidence_count": len(case["required_evidence"]),
            "covered_evidence_count": sum(
                any(finding["claim_key"] == gold["claim_key"] and any(citation["source_id"] in gold["allowed_source_ids"] and _citation_valid(case, citation) for citation in finding["citations"]) for finding in output["findings"])
                for gold in case["required_evidence"]
            ),
            "expected_escalation": case["expected_escalation"],
            "observed_escalation": output["escalation_status"],
            "policy_assessment_status": output["policy_assessment_status"],
            "policy_violations": output["policy_violations"],
        })
    return details


def render_markdown(scorecard: dict[str, Any]) -> str:
    lines = [
        "# EDD Benchmark Scorecard", "",
        f"- Benchmark: `{scorecard['benchmark_id']}` v{scorecard['benchmark_version']}",
        f"- Run ID: `{scorecard['run_metadata']['run_id']}`",
        f"- System: {scorecard['run_metadata']['system_name']} ({scorecard['run_metadata']['system_version']})",
        f"- Model: {scorecard['run_metadata']['model_provider']} / {scorecard['run_metadata']['model_version']}",
        f"- Cases: {scorecard['case_count']}", "",
        "| Metric | Value | Numerator | Denominator | Status | Missing | Reason |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for metric in scorecard["metrics"]:
        value = "N/A" if metric["value"] is None else f"{metric['value']:.4f}"
        numerator = "N/A" if metric["numerator"] is None else str(metric["numerator"])
        denominator = "N/A" if metric["denominator"] is None else str(metric["denominator"])
        reason = metric["reason"] or ""
        lines.append(f"| {metric['metric']} | {value} | {numerator} | {denominator} | {metric['status']} | {metric['missing_count']} | {reason} |")
    lines.extend(["", "## Case details", "", "| Case | Findings | Unsupported | Evidence covered | Escalation expected / observed | Policy assessment / violations |", "| --- | ---: | ---: | --- | --- | --- |"])
    for case in scorecard["case_details"]:
        lines.append(
            f"| {case['case_id']} | {case['finding_count']} | {case['unsupported_claim_count']} | "
            f"{case['covered_evidence_count']}/{case['required_evidence_count']} | "
            f"{case['expected_escalation']} / {case['observed_escalation']} | "
            f"{case['policy_assessment_status']} / {', '.join(case['policy_violations']) or 'none'} |"
        )
    lines.extend(["", "## Aggregate", "", "No aggregate score is calculated.", ""])
    return "\n".join(lines)
