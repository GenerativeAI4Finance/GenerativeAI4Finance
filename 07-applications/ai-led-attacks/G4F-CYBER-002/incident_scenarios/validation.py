"""Load and validate controlled incident scenario JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

TASK_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = TASK_ROOT / "schema" / "incident-scenario.schema.json"


def load_schema() -> dict[str, Any]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_scenario(scenario: dict[str, Any]) -> None:
    """Validate the JSON Schema and cross-field references before simulation."""
    errors = sorted(Draft202012Validator(load_schema()).iter_errors(scenario), key=lambda err: list(err.path))
    if errors:
        details = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise ValueError(f"invalid scenario: {details}")

    asset_ids = [asset["asset_id"] for asset in scenario["assets"]]
    event_ids = [event["event_id"] for event in scenario["simulated_events"]]
    evidence_ids = [item["evidence_id"] for item in scenario["evidence"]]
    if len(set(asset_ids)) != len(asset_ids):
        raise ValueError("asset_id values must be unique")
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("event_id values must be unique")
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("evidence_id values must be unique")
    event_id_set = set(event_ids)
    if any(event["target_asset_id"] not in asset_ids for event in scenario["simulated_events"]):
        raise ValueError("every simulated event must reference a declared asset")
    for section_name in ["expected_detections", "safe_response", "evidence"]:
        if any(item["source_event_id"] not in event_id_set for item in scenario[section_name]):
            raise ValueError(f"every {section_name} item must reference a declared event")


def load_scenarios(directory: Path | None = None) -> list[dict[str, Any]]:
    examples = directory or (TASK_ROOT / "examples")
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(examples.glob("*.json"))]
