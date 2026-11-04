"""Fixed-order orchestration and deterministic trace logging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from .agents import AgentRole, EntityMatcher, EvidenceAnalyst, Reviewer, SourceCollector


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SWARM_ROOT = PACKAGE_ROOT.parent
DEFAULT_CONFIG = PACKAGE_ROOT / "config" / "workflow.json"
SCENARIO_ROOT = SWARM_ROOT / "G4F-SW-002" / "examples"


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def available_scenarios() -> dict[str, Path]:
    return {
        scenario["scenario_id"]: path
        for path in sorted(SCENARIO_ROOT.glob("*.json"))
        for scenario in [load_json(path)]
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _run_id(scenario: dict[str, Any], config: dict[str, Any]) -> str:
    content = _canonical_json({"scenario": scenario, "config": config}).encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def _check_scenario(scenario: dict[str, Any]) -> None:
    if scenario.get("synthetic") is not True:
        raise ValueError("The baseline accepts explicitly synthetic scenarios only.")
    required = {"scenario_id", "title", "synthetic_inputs", "allowed_tools", "ground_truth"}
    missing = required - scenario.keys()
    if missing:
        raise ValueError(f"Scenario is missing required fields: {', '.join(sorted(missing))}.")
    if not isinstance(scenario["synthetic_inputs"], list) or not scenario["synthetic_inputs"]:
        raise ValueError("Scenario must contain a non-empty synthetic_inputs array.")


def _invoke(role: AgentRole, role_input: dict[str, Any], trace: list[dict[str, Any]]) -> dict[str, Any]:
    output = role.run(role_input)
    trace.append({"step_type": "agent", "agent": role.name, "input": role_input, "output": output})
    return output


def _mock_tool_action(
    tool_name: str,
    scenario: dict[str, Any],
    reviewer_output: dict[str, Any],
    trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if reviewer_output["recommended_tool_action"] is None:
        return None
    if tool_name not in scenario["allowed_tools"]:
        raise PermissionError(f"Reviewer requested tool not allowed by scenario: {tool_name}.")
    tool_input = {
        "scenario_id": scenario["scenario_id"],
        "requested_action": tool_name,
        "disposition": reviewer_output["disposition"],
    }
    tool_output = {
        "event_id": f"MOCK-REVIEW-{scenario['scenario_id'][-3:]}",
        "status": "queued_for_human_review",
        "synthetic": True,
    }
    trace.append({"step_type": "mock_tool", "tool": tool_name, "input": tool_input, "output": tool_output})
    return tool_output


def _unique_lineage(source_id: str, sources_by_id: dict[str, dict[str, Any]]) -> str:
    visited: set[str] = set()
    current = source_id
    while current in sources_by_id and sources_by_id[current]["duplicate_of"] is not None:
        if current in visited:
            break
        visited.add(current)
        current = sources_by_id[current]["duplicate_of"]
    return current


def run_scenario(
    scenario: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    roles: Sequence[AgentRole] | None = None,
) -> dict[str, Any]:
    """Run the deterministic source→match→analysis→review workflow.

    Ground truth is used only to guard against malformed fixture input and is
    deliberately excluded from all role inputs and their trace entries.
    """
    _check_scenario(scenario)
    config = config or load_json(DEFAULT_CONFIG)
    profile = config["scenario_profiles"].get(scenario["scenario_id"])
    if profile is None:
        raise ValueError(f"No workflow profile for {scenario['scenario_id']}.")
    role_map = {role.name: role for role in (roles or [SourceCollector(), EntityMatcher(), EvidenceAnalyst(), Reviewer()])}
    order = config["workflow_order"]
    fixed_order = ["source_collector", "entity_matcher", "evidence_analyst", "reviewer"]
    if order != fixed_order or set(order) != set(role_map) or len(order) != len(role_map):
        raise ValueError("workflow_order must preserve the supported fixed four-role sequence.")

    trace: list[dict[str, Any]] = []
    collector_input = {
        "scenario_id": scenario["scenario_id"],
        "synthetic_inputs": scenario["synthetic_inputs"],
    }
    collected = _invoke(role_map["source_collector"], collector_input, trace)

    matcher_input = {
        "subject": profile["subject"],
        "profile": profile,
        "sources": collected["sources"],
    }
    entity_match = _invoke(role_map["entity_matcher"], matcher_input, trace)

    analyst_input = {"profile": profile, "sources": collected["sources"], "config": config}
    analysis = _invoke(role_map["evidence_analyst"], analyst_input, trace)

    reviewer_input = {
        "profile": profile,
        "entity_match": entity_match,
        "analysis": analysis,
        "allowed_tools": scenario["allowed_tools"],
    }
    review = _invoke(role_map["reviewer"], reviewer_input, trace)
    mock_review_event = _mock_tool_action(
        review["recommended_tool_action"], scenario, review, trace
    ) if review["recommended_tool_action"] else None

    source_by_id = {source["source_id"]: source for source in collected["sources"] if source["source_id"]}
    unique_evidence_lineages = sorted({
        _unique_lineage(source["source_id"], source_by_id)
        for source in collected["sources"] if source["source_id"]
    })
    unresolved = list(analysis["unresolved_issues"])
    if entity_match["match_status"] == "possible_name_only_match":
        unresolved.append({
            "issue": "identity_match_unresolved_name_only",
            "status": "human_review_required",
            "source_references": entity_match["matching_sources"],
        })

    report = {
        "report_version": "1.0.0",
        "run_id": _run_id(scenario, config),
        "scenario_id": scenario["scenario_id"],
        "scenario_version": scenario.get("scenario_version"),
        "synthetic": True,
        "subject": entity_match["subject"],
        "subject_kind": entity_match["subject_kind"],
        "entity_match": entity_match,
        "findings": analysis["findings"],
        "source_references": [source["source_reference"] for source in collected["sources"]],
        "evidence_lineage": {
            "unique_source_lineages": unique_evidence_lineages,
            "duplicate_records": analysis["duplicate_records"],
        },
        "uncertainty": [entity_match["uncertainty"]],
        "unresolved_issues": unresolved,
        "review": {
            "status": review["status"],
            "disposition": review["disposition"],
            "rationale": review["rationale"],
            "reviewer_decision": review["reviewer_decision"],
            "consensus_is_proof": review["consensus_is_proof"],
            "mock_review_event": mock_review_event,
        },
        "limitations": [
            "All records are fictional scenario inputs, not independently verified sources.",
            "The rule-based role outputs are candidate observations, not a final EDD decision.",
            "Agreement among agents is not independent corroboration or proof of truth.",
        ],
    }
    return {"report": report, "trace": trace}
