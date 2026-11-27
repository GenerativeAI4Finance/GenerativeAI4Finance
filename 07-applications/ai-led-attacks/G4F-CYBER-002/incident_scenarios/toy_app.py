"""Bounded deterministic simulator for declarative local incident scenarios."""

from __future__ import annotations

from typing import Any

from .validation import validate_scenario


def run_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Simulate allowlisted events without network, shell, or real integrations."""
    validate_scenario(scenario)
    if scenario["environment"] != {
        "execution_mode": "local_toy_app",
        "network_access": False,
        "production_access": False,
        "external_tools": False,
    }:
        raise ValueError("scenario environment must be strictly local and isolated")

    assets = {asset["asset_id"] for asset in scenario["assets"]}
    detections: list[dict[str, str]] = []
    responses: list[dict[str, str]] = []
    event_log: list[dict[str, str]] = []

    for event in scenario["simulated_events"]:
        if event["target_asset_id"] not in assets:
            raise ValueError(f"event targets undeclared asset: {event['target_asset_id']}")
        event_id = event["event_id"]
        kind = event["event_type"]
        params = event["parameters"]
        detection: str | None = None
        action = "continue_safe_read"
        result_code = "read_only_simulation_completed"

        if kind == "untrusted_content" and params["contains_untrusted_instruction"]:
            detection = "untrusted_content_detected"
            action = "flag_for_review"
            result_code = "content_kept_as_untrusted_evidence"
        elif kind == "identity_check" and not params["authorized"]:
            detection = "unauthorized_identity_detected"
            action = "deny_access"
            result_code = "access_denied_and_logged"
        elif kind == "resource_burst" and params["request_count"] > params["configured_limit"]:
            detection = "resource_limit_exceeded"
            action = "apply_local_rate_limit"
            result_code = "simulated_requests_limited"

        if detection:
            detections.append({"detection_id": detection, "source_event_id": event_id})
        responses.append({"source_event_id": event_id, "action": action, "result_code": result_code})
        event_log.append({"source_event_id": event_id, "evidence_type": "toy_app_event_log"})

    expected_detections = sorted(
        scenario["expected_detections"], key=lambda item: (item["source_event_id"], item["detection_id"])
    )
    actual_detections = sorted(detections, key=lambda item: (item["source_event_id"], item["detection_id"]))
    expected_responses = sorted(
        scenario["safe_response"], key=lambda item: (item["source_event_id"], item["action"])
    )
    actual_responses = sorted(responses, key=lambda item: (item["source_event_id"], item["action"]))
    passed = expected_detections == actual_detections and expected_responses == actual_responses
    return {
        "scenario_id": scenario["scenario_id"],
        "seed": scenario["seed"],
        "detections": actual_detections,
        "responses": actual_responses,
        "event_log": event_log,
        "passed": passed,
    }
