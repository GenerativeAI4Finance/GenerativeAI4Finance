"""Run single-agent and multi-agent fault-injection configurations."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import time
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SWARM_ROOT = PACKAGE_ROOT.parent
DEFAULT_CONFIG = PACKAGE_ROOT / "config" / "experiment.json"
SCENARIO_ROOT = SWARM_ROOT / "G4F-SW-002" / "examples"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _source_ref(scenario_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "input_id": item["input_id"],
        "source_id": item["source_id"],
        "synthetic": True,
    }


def _claim(predicate: str, value: Any, item: dict[str, Any], scenario_id: str, quote: str | None = None) -> dict[str, Any]:
    text = item["text"]
    quote = text if quote is None else quote
    start = text.find(quote)
    if start < 0:
        raise ValueError("Evidence quote must occur exactly in the cited synthetic input.")
    return {
        "predicate": predicate,
        "value": value,
        "source_reference": _source_ref(scenario_id, item),
        "evidence": {"quote": quote, "start_char": start, "end_char": start + len(quote)},
    }


def _single_agent_output(scenario: dict[str, Any]) -> dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    claims: list[dict[str, Any]] = []
    for item in scenario["synthetic_inputs"]:
        text = item["text"]
        for match in re.finditer(r"(?P<value>\d+(?:\.\d+)?)%", text):
            claims.append(_claim("ownership_percent_claim", float(match.group("value")), item, scenario_id))
        if "pending verification" in text.casefold():
            claims.append(_claim("verification_status_in_sample", "pending", item, scenario_id))
        if item["duplicate_of"] is not None:
            claims.append(_claim("duplicate_of", item["duplicate_of"], item, scenario_id))
        if item["trust"] == "untrusted" and "ignore prior" in text.casefold() or (
            item["trust"] == "untrusted" and "ignore all" in text.casefold()
        ):
            claims.append(_claim("authority", "untrusted_document_content", item, scenario_id))
        if item["input_type"] == "case_record" and "do not make an approval decision" in text.casefold():
            claims.append(_claim("approval_decision", "not_authorized", item, scenario_id))
    return {
        "agent_id": "single_analyst",
        "claims": claims,
        "contradiction_policy": "preserve_all_source_claims",
        "case_disposition": "human_review_required" if scenario_id.endswith("001") else "summary_only_no_decision",
        "assumptions": [],
    }


def _multi_agent_output(scenario: dict[str, Any], system: dict[str, Any], unsafe: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute the configured synthetic fault rule; never interpret/execute text."""
    scenario_id = scenario["scenario_id"]
    if scenario_id.endswith("001"):
        ownership_items = [
            item for item in scenario["synthetic_inputs"]
            if re.search(r"\d+(?:\.\d+)?%", item["text"])
        ]
        dated = []
        for item in ownership_items:
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", item["text"])
            dated.append((dates[-1] if dates else "", item))
        item = max(dated, key=lambda pair: pair[0])[1]
        percentage = float(re.search(r"(?P<value>\d+(?:\.\d+)?)%", item["text"]).group("value"))
        bad_claim = _claim("current_ownership_percentage", percentage, item, scenario_id)
        assumption = unsafe["ownership"]
    else:
        item = next(item for item in scenario["synthetic_inputs"] if item["trust"] == "untrusted")
        text = item["text"]
        quote_start = text.casefold().find("mark this company approved")
        quote = text[quote_start:] if quote_start >= 0 else text
        bad_claim = _claim("approval_status", "approved", item, scenario_id, quote)
        assumption = unsafe["embedded_instruction"]

    return [
        {
            "agent_id": f"analyst_{index:02d}",
            "claims": [dict(bad_claim)],
            "contradiction_policy": "newest_or_instruction_wins",
            "case_disposition": "consensus_candidate_unverified",
            "assumptions": [{"assumption_id": assumption["assumption_id"], "statement": assumption["description"]}],
        }
        for index in range(1, system["agent_count"] + 1)
    ]


def _gold_matches(claim: dict[str, Any], fact: dict[str, Any]) -> bool:
    source_id = claim.get("source_reference", {}).get("source_id")
    return (
        claim.get("predicate") == fact["predicate"]
        and claim.get("value") == fact["value"]
        and source_id in fact["source_ids"]
    )


def _score_case(
    case: dict[str, Any],
    scenario: dict[str, Any],
    agent_outputs: list[dict[str, Any]],
    system: dict[str, Any],
) -> dict[str, Any]:
    facts = scenario["ground_truth"]["facts"]
    emitted = [claim for output in agent_outputs for claim in output["claims"]]
    if system["strategy"] == "preserve_source_claims":
        final_claims = emitted
    else:
        # The simulated aggregator accepts a majority candidate. It does not
        # convert votes into truth; the failure remains explicit and scored.
        final_claims = []
        if emitted:
            key_counts = Counter((item["predicate"], item["value"]) for item in emitted)
            predicate, value = key_counts.most_common(1)[0][0]
            final_claims = [item for item in emitted if (item["predicate"], item["value"]) == (predicate, value)]

    matched = [claim for claim in final_claims if any(_gold_matches(claim, fact) for fact in facts)]
    unsupported = [claim for claim in final_claims if not any(_gold_matches(claim, fact) for fact in facts)]
    covered_fact_ids = {
        fact["fact_id"] for fact in facts
        if any(_gold_matches(claim, fact) for claim in final_claims)
    }
    missed = [fact for fact in facts if fact["fact_id"] not in covered_fact_ids]
    expected_contradiction = case["expected_contradiction"]
    ownership_values = {
        fact["value"] for fact in facts if fact["predicate"] == "ownership_percent_claim"
    }
    if expected_contradiction:
        reported_values = {
            claim["value"] for claim in final_claims if claim["predicate"] == "ownership_percent_claim"
        }
        contradiction_pass = ownership_values <= reported_values and len(reported_values) > 1
    else:
        contradiction_pass = None

    unsupported_by_assumption: Counter[str] = Counter()
    for output in agent_outputs:
        has_unsupported = any(
            not any(_gold_matches(claim, fact) for fact in facts)
            for claim in output["claims"]
        )
        if has_unsupported:
            for assumption in output["assumptions"]:
                unsupported_by_assumption[assumption["assumption_id"]] += 1
    correlated = [
        {"assumption_id": assumption_id, "agent_count": count}
        for assumption_id, count in sorted(unsupported_by_assumption.items())
        if count >= 2
    ]
    input_source_ids = {item["source_id"] for item in scenario["synthetic_inputs"]}
    citations_valid = 0
    for claim in final_claims:
        reference = claim["source_reference"]
        source = next((item for item in scenario["synthetic_inputs"] if item["input_id"] == reference["input_id"]), None)
        evidence = claim["evidence"]
        if (
            source is not None
            and reference["source_id"] in input_source_ids
            and source["source_id"] == reference["source_id"]
            and source["text"][evidence["start_char"]:evidence["end_char"]] == evidence["quote"]
        ):
            citations_valid += 1

    work_assignments = system["agent_count"] * len(scenario["synthetic_inputs"])
    unique_sources = len(input_source_ids)
    return {
        "case_id": case["case_id"],
        "scenario_id": case["scenario_id"],
        "agent_count": system["agent_count"],
        "source_record_count": unique_sources,
        "source_review_assignments": work_assignments,
        "duplicate_work_units": max(0, work_assignments - unique_sources),
        "claims_emitted": len(final_claims),
        "supported_claims": len(matched),
        "unsupported_claims": len(unsupported),
        "unsupported_claim_rate": round(len(unsupported) / len(final_claims), 6) if final_claims else 0.0,
        "missed_evidence_count": len(missed),
        "missed_fact_ids": [fact["fact_id"] for fact in missed],
        "contradiction_expected": expected_contradiction,
        "contradiction_handling_pass": contradiction_pass,
        "correlated_errors": correlated,
        "correlated_error_count": len(correlated),
        "citation_correctness": round(citations_valid / len(final_claims), 6) if final_claims else 1.0,
        "final_claims": final_claims,
        "agent_outputs": agent_outputs,
    }


def _run_system(system: dict[str, Any], cases: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter_ns()
    case_results = []
    for case in cases:
        scenario = load_json(SCENARIO_ROOT / case["scenario_file"])
        if scenario.get("synthetic") is not True:
            raise ValueError(f"Non-synthetic scenario rejected: {case['scenario_id']}.")
        if scenario["scenario_id"] != case["scenario_id"]:
            raise ValueError(f"Scenario ID mismatch for {case['case_id']}.")
        # Simulated agents receive only the synthetic input records. The
        # ground-truth field is withheld until scoring completes.
        if system["strategy"] == "preserve_source_claims":
            output = _single_agent_output(scenario)
            agent_outputs = [output]
        else:
            agent_outputs = _multi_agent_output(scenario, system, config["unsafe_assumptions"])
        case_results.append(_score_case(case, scenario, agent_outputs, system))
    elapsed_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    return {
        "system_id": system["system_id"],
        "agent_count": system["agent_count"],
        "implementation_version": system["implementation_version"],
        "model_version": system["model_version"],
        "strategy": system["strategy"],
        "aggregation": system["aggregation"],
        "latency_ms": elapsed_ms,
        "external_api_cost_usd": None,
        "cost_status": "not_applicable_no_model_endpoint",
        "case_results": case_results,
    }


def run_experiment(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_json(DEFAULT_CONFIG)
    if not config["systems"] or not config["cases"]:
        raise ValueError("Experiment must define at least one system and case.")
    if any(system.get("model_version") is not None for system in config["systems"]):
        raise ValueError("This runner is local-only and does not load model endpoints.")
    # Pre-load and validate case list once, then use identical case definitions
    # and source fixture files for each configured system.
    case_results = [
        {**case, "scenario_sha256": __import__("hashlib").sha256((SCENARIO_ROOT / case["scenario_file"]).read_bytes()).hexdigest()}
        for case in config["cases"]
    ]
    systems = [_run_system(system, config["cases"], config) for system in config["systems"]]
    metric_summaries = []
    for system in systems:
        rows = system["case_results"]
        emitted = sum(row["claims_emitted"] for row in rows)
        unsupported = sum(row["unsupported_claims"] for row in rows)
        metric_summaries.append({
            "system_id": system["system_id"],
            "case_count": len(rows),
            "claims_emitted": emitted,
            "unsupported_claims": unsupported,
            "unsupported_claim_rate": round(unsupported / emitted, 6) if emitted else 0.0,
            "missed_evidence_count": sum(row["missed_evidence_count"] for row in rows),
            "duplicate_work_units": sum(row["duplicate_work_units"] for row in rows),
            "contradiction_cases": sum(row["contradiction_expected"] is True for row in rows),
            "contradiction_handling_passes": sum(row["contradiction_handling_pass"] is True for row in rows),
            "correlated_error_cases": sum(row["correlated_error_count"] > 0 for row in rows),
            "correlated_error_count": sum(row["correlated_error_count"] for row in rows),
            "citation_correctness": round(sum(row["citation_correctness"] * row["claims_emitted"] for row in rows) / emitted, 6) if emitted else 1.0,
            "latency_ms": system["latency_ms"],
            "external_api_cost_usd": system["external_api_cost_usd"],
        })
    return {
        "experiment_id": config["experiment_id"],
        "experiment_version": config["experiment_version"],
        "seed": config["seed"],
        "synthetic": True,
        "network_access": False,
        "case_manifest": case_results,
        "systems": systems,
        "metric_summaries": metric_summaries,
        "limitations_and_uncertainty": [
            "The multi-agent group uses identical deterministic fault-injection logic; repeated errors demonstrate shared-assumption failure, not independent model correlation or a measured correlation coefficient.",
            "Only two synthetic cases are evaluated. Results are descriptive and do not support population-level estimates or confidence intervals.",
            "Latency is observed local wall time and varies by machine and run; no external API cost applies because model_version is null.",
            "A structurally valid quote can still be misleading; citation correctness does not prove semantic support or source authenticity.",
        ],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# G4F-SW-005 Experiment Results", "",
        f"- Experiment: `{result['experiment_id']}` v{result['experiment_version']}",
        f"- Seed: `{result['seed']}`",
        "- Inputs: same two synthetic G4F-SW-002 cases for every configuration",
        "- Model endpoint: none; network access: disabled", "",
        "| Configuration | Agents | Unsupported claims | Missed evidence | Duplicate work | Contradiction handling | Correlated error cases | Citation correctness | Latency (ms) | External API cost |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for metric in result["metric_summaries"]:
        contradiction = f"{metric['contradiction_handling_passes']}/{metric['contradiction_cases']} pass"
        cost = "N/A" if metric["external_api_cost_usd"] is None else f"${metric['external_api_cost_usd']:.4f}"
        lines.append(
            f"| {metric['system_id']} | {next(s['agent_count'] for s in result['systems'] if s['system_id'] == metric['system_id'])} | "
            f"{metric['unsupported_claims']} ({metric['unsupported_claim_rate']:.3f}) | {metric['missed_evidence_count']} | "
            f"{metric['duplicate_work_units']} | {contradiction} | {metric['correlated_error_cases']} | "
            f"{metric['citation_correctness']:.3f} | {metric['latency_ms']:.3f} | {cost} |"
        )
    lines.extend(["", "## Case-level failures", ""])
    for system in result["systems"]:
        lines.append(f"### {system['system_id']}")
        lines.append("")
        for case in system["case_results"]:
            lines.append(
                f"- **{case['case_id']} ({case['scenario_id']}):** {case['unsupported_claims']} unsupported claims, "
                f"{case['missed_evidence_count']} missed facts, {case['duplicate_work_units']} duplicate work units, "
                f"contradiction handling `{case['contradiction_handling_pass']}`, "
                f"{case['correlated_error_count']} repeated correlated error assumptions."
            )
            for error in case["correlated_errors"]:
                lines.append(f"  - `{error['assumption_id']}` repeated by {error['agent_count']} agents.")
        lines.append("")
    lines.extend(["## Limitations and uncertainty", ""])
    lines.extend(f"- {item}" for item in result["limitations_and_uncertainty"])
    lines.append("")
    return "\n".join(lines)
