"""Small deterministic roles with a replaceable JSON-in/JSON-out interface."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol


class AgentRole(Protocol):
    """Interface implemented by each replaceable simulated role."""

    name: str

    def run(self, role_input: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON-compatible result for the supplied role input."""


@dataclass
class SourceCollector:
    name: str = "source_collector"

    def run(self, role_input: dict[str, Any]) -> dict[str, Any]:
        scenario_id = role_input["scenario_id"]
        sources = []
        for item in role_input["synthetic_inputs"]:
            sources.append({
                "input_id": item["input_id"],
                "source_id": item["source_id"],
                "source_type": item["input_type"],
                "trust": item["trust"],
                "duplicate_of": item["duplicate_of"],
                "text": item["text"],
                "source_reference": {
                    "scenario_id": scenario_id,
                    "input_id": item["input_id"],
                    "source_id": item["source_id"],
                    "synthetic": True,
                },
            })
        return {"sources": sources, "source_count": len(sources)}


@dataclass
class EntityMatcher:
    name: str = "entity_matcher"

    def run(self, role_input: dict[str, Any]) -> dict[str, Any]:
        subject = role_input["subject"]
        subject_folded = subject.casefold()
        matches = [
            source["source_reference"]
            for source in role_input["sources"]
            if subject_folded in source["text"].casefold()
        ]
        profile = role_input["profile"]
        if not matches:
            status = "not_observed_in_supplied_sources"
            uncertainty = "No exact configured subject string was found in the supplied synthetic inputs."
        elif profile["entity_kind"] == "individual":
            status = "possible_name_only_match"
            uncertainty = "Name presence alone is insufficient to establish an individual's identity."
        else:
            status = "subject_name_observed"
            uncertainty = "Exact name presence is not independent identity verification."
        return {
            "subject": subject,
            "subject_kind": profile["entity_kind"],
            "match_status": status,
            "matching_sources": matches,
            "uncertainty": uncertainty,
        }


@dataclass
class EvidenceAnalyst:
    name: str = "evidence_analyst"

    def run(self, role_input: dict[str, Any]) -> dict[str, Any]:
        sources = role_input["sources"]
        profile = role_input["profile"]
        config = role_input["config"]
        findings: list[dict[str, Any]] = []
        duplicate_records: list[dict[str, Any]] = []
        untrusted_instructions: list[dict[str, Any]] = []
        ownership_values: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []

        for source in sources:
            text = source["text"]
            source_ref = source["source_reference"]
            duplicate_of = source["duplicate_of"]
            if duplicate_of is not None:
                duplicate_records.append({
                    "source_id": source["source_id"],
                    "duplicate_of": duplicate_of,
                    "source_reference": source_ref,
                })

            if profile["entity_kind"] == "entity":
                for match in re.finditer(config["ownership_pattern"], text):
                    value = float(match.group("value"))
                    claim_start, claim_end = 0, len(text)
                    claim = {
                        "claim_type": "source_claim",
                        "predicate": "ownership_percentage_claim",
                        "value": value,
                        "statement": text,
                        "source_reference": source_ref,
                        "evidence": {"quote": text[claim_start:claim_end], "start_char": claim_start, "end_char": claim_end},
                        "trust": source["trust"],
                        "duplicate_of": duplicate_of,
                    }
                    findings.append(claim)
                    ownership_values.append({
                        "value": value,
                        "source_id": source["source_id"],
                        "duplicate_of": duplicate_of,
                    })

            folded = text.casefold()
            marker = next((term for term in config["instruction_markers"] if term.casefold() in folded), None)
            if marker is not None:
                index = folded.index(marker.casefold())
                untrusted_instructions.append({
                    "source_reference": source_ref,
                    "trust": source["trust"],
                    "quote": text[index:],
                    "start_char": index,
                    "end_char": len(text),
                    "treated_as": "untrusted_document_content",
                })

            if any(marker.casefold() in folded for marker in config["pending_markers"]):
                findings.append({
                    "claim_type": "source_claim",
                    "predicate": "verification_status_in_sample",
                    "value": "pending",
                    "statement": text,
                    "source_reference": source_ref,
                    "evidence": {"quote": text, "start_char": 0, "end_char": len(text)},
                    "trust": source["trust"],
                    "duplicate_of": duplicate_of,
                })

        distinct_values = {entry["value"] for entry in ownership_values}
        has_conflict = len(distinct_values) > 1
        if has_conflict:
            unresolved.append({
                "issue": "conflicting_ownership_claims",
                "values": sorted(distinct_values),
                "source_ids": sorted({entry["source_id"] for entry in ownership_values}),
                "status": "unresolved",
            })
        if untrusted_instructions:
            unresolved.append({
                "issue": "instruction_like_content_in_untrusted_document",
                "source_ids": sorted({item["source_reference"]["source_id"] for item in untrusted_instructions}),
                "status": "flagged_not_followed",
            })
        return {
            "findings": findings,
            "ownership_claims": ownership_values,
            "ownership_conflict_detected": has_conflict,
            "duplicate_records": duplicate_records,
            "untrusted_instructions": untrusted_instructions,
            "unresolved_issues": unresolved,
        }


@dataclass
class Reviewer:
    name: str = "reviewer"

    def run(self, role_input: dict[str, Any]) -> dict[str, Any]:
        profile = role_input["profile"]
        match = role_input["entity_match"]
        analysis = role_input["analysis"]
        policy = profile["review_policy"]
        allowed_tools = role_input.get("allowed_tools", [])
        escalate = (
            policy == "escalate_material_conflicts" and analysis["ownership_conflict_detected"]
        ) or (
            policy == "escalate_name_only_matches" and match["match_status"] == "possible_name_only_match"
        )
        if escalate:
            status = "human_review_required"
            disposition = "human_review_required_no_final_decision"
            action = "create_mock_review_request" if "create_mock_review_request" in allowed_tools else None
            rationale = "A configured materiality rule requires a human to review unresolved evidence."
        elif policy == "ignore_untrusted_instructions" and analysis["untrusted_instructions"]:
            status = "summary_only_no_decision"
            disposition = "summarize_source_claims_without_approval"
            action = None
            rationale = "Instruction-like document text is untrusted and cannot authorize an approval decision."
        else:
            status = "completed_with_uncertainty"
            disposition = "no_automated_final_decision"
            action = None
            rationale = "The baseline reports supplied claims without treating agreement as proof."
        return {
            "status": status,
            "disposition": disposition,
            "recommended_tool_action": action,
            "rationale": rationale,
            "consensus_is_proof": False,
            "reviewer_decision": None,
        }
