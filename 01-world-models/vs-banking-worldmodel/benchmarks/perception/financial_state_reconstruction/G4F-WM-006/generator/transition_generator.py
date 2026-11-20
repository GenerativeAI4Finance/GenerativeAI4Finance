"""Generate and replay fictional, event-driven financial-state trajectories."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "transition_scenarios.json"
DEFAULT_OUTPUT = ROOT / "data" / "sample"
EVENT_TYPES = {
    "scheduled_payment", "payment_delay", "liquidity_shock", "rate_change",
    "new_credit_exposure", "recovery_payment", "liquidity_normalization",
}
PATH_TYPES = {"normal", "stress", "recovery"}


def _load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config.get("seed"), int) or config["seed"] < 0:
        raise ValueError("seed must be a non-negative integer")
    if not config.get("scenarios"):
        raise ValueError("at least one scenario is required")
    for scenario in config["scenarios"]:
        if scenario.get("path_type") not in PATH_TYPES:
            raise ValueError(f"unsupported path_type in {scenario.get('scenario_id')}")
        previous_day = 0
        for event in scenario.get("events", []):
            day = event.get("days_after_start")
            if not isinstance(day, int) or day <= previous_day:
                raise ValueError("event days_after_start must be strictly increasing positive integers")
            if event.get("event_type") not in EVENT_TYPES:
                raise ValueError(f"unsupported event_type: {event.get('event_type')}")
            previous_day = day
    return config


def _sample_initial_state(rng: np.random.Generator, ranges: dict[str, list[float]]) -> dict[str, Any]:
    state = {
        "account_status": "current",
        "balance_usd": round(float(rng.uniform(*ranges["balance_usd"])), 2),
        "monthly_revenue_usd": round(float(rng.uniform(*ranges["monthly_revenue_usd"])), 2),
        "interest_rate_pct": round(float(rng.uniform(*ranges["interest_rate_pct"])), 4),
        "monthly_debt_service_usd": round(float(rng.uniform(*ranges["monthly_debt_service_usd"])), 2),
        "days_past_due": 0,
    }
    state["debt_to_income_ratio"] = round(state["monthly_debt_service_usd"] / state["monthly_revenue_usd"], 6)
    return state


def _apply_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Apply one configured event; return a new state without mutating input."""
    result = dict(state)
    kind = event["event_type"]

    if kind == "scheduled_payment":
        if event.get("payment_status") == "received":
            result["balance_usd"] = max(0.0, result["balance_usd"] - event.get("payment_amount_usd", 0.0))
        result["account_status"] = "current" if result["days_past_due"] == 0 else "delinquent"
    elif kind == "payment_delay":
        result["days_past_due"] += event.get("days_past_due_increment", 30)
        result["account_status"] = "delinquent"
    elif kind in {"liquidity_shock", "liquidity_normalization"}:
        result["monthly_revenue_usd"] *= event["revenue_multiplier"]
        if result["days_past_due"] == 0:
            result["account_status"] = "liquidity_stress" if kind == "liquidity_shock" else "current"
    elif kind == "rate_change":
        old_rate = result["interest_rate_pct"]
        new_rate = old_rate + event["rate_change_pct_points"]
        if new_rate < 0 or new_rate > 100:
            raise ValueError("rate change would put interest_rate_pct outside [0, 100]")
        result["interest_rate_pct"] = new_rate
        if old_rate > 0:
            result["monthly_debt_service_usd"] *= new_rate / old_rate
    elif kind == "new_credit_exposure":
        result["balance_usd"] += event["exposure_usd"]
        result["monthly_debt_service_usd"] += event["additional_monthly_service_usd"]
    elif kind == "recovery_payment":
        result["balance_usd"] = max(0.0, result["balance_usd"] - event.get("payment_amount_usd", 0.0))
        result["days_past_due"] = 0
        result["account_status"] = "cured"

    result["balance_usd"] = round(result["balance_usd"], 2)
    result["monthly_revenue_usd"] = round(result["monthly_revenue_usd"], 2)
    result["interest_rate_pct"] = round(result["interest_rate_pct"], 4)
    result["monthly_debt_service_usd"] = round(result["monthly_debt_service_usd"], 2)
    if result["monthly_revenue_usd"] <= 0:
        raise ValueError("monthly_revenue_usd must remain positive")
    result["debt_to_income_ratio"] = round(result["monthly_debt_service_usd"] / result["monthly_revenue_usd"], 6)
    return result


def replay_scenario(config: dict[str, Any], scenario: dict[str, Any], initial_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Replay the event sequence from an explicit initial state."""
    start = datetime.fromisoformat(config["start_timestamp"].replace("Z", "+00:00"))
    if start.tzinfo is None:
        raise ValueError("start_timestamp must include a UTC offset")
    state = dict(initial_state)
    records: list[dict[str, Any]] = []
    for sequence, event in enumerate(scenario["events"], start=1):
        if event["event_type"] not in EVENT_TYPES:
            raise ValueError(f"unsupported event_type: {event['event_type']}")
        timestamp = start + timedelta(days=event["days_after_start"])
        before = dict(state)
        state = _apply_event(state, event)
        attributes = {key: value for key, value in event.items() if key not in {"days_after_start", "event_type", "action"}}
        records.append({
            "schema_version": "1.0.0",
            "transition_id": f"{scenario['scenario_id']}-T{sequence:03d}",
            "scenario_id": scenario["scenario_id"],
            "path_type": scenario["path_type"],
            "entity_id": scenario["entity_id"],
            "sequence": sequence,
            "transition_timestamp_utc": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": {"event_type": event["event_type"], "attributes": attributes},
            "action": event.get("action"),
            "initial_state": before,
            "resulting_state": dict(state),
            "synthetic": True,
        })
    return records


def generate_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    rng = np.random.default_rng(config["seed"])
    records: list[dict[str, Any]] = []
    for scenario in config["scenarios"]:
        initial_state = _sample_initial_state(rng, config["initial_state_ranges"])
        records.extend(replay_scenario(config, scenario, initial_state))
    return records


def write_dataset(config_path: Path = DEFAULT_CONFIG, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    config = _load_config(config_path)
    records = generate_records(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectories_path = output_dir / "example_trajectories.json"
    csv_path = output_dir / "transitions.csv"
    trajectories_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    flat = [{
        "transition_id": row["transition_id"], "scenario_id": row["scenario_id"],
        "path_type": row["path_type"], "entity_id": row["entity_id"],
        "sequence": row["sequence"], "transition_timestamp_utc": row["transition_timestamp_utc"],
        "event_type": row["event"]["event_type"], "event_attributes_json": json.dumps(row["event"]["attributes"], sort_keys=True),
        "action": row["action"], "initial_state_json": json.dumps(row["initial_state"], sort_keys=True),
        "resulting_state_json": json.dumps(row["resulting_state"], sort_keys=True), "synthetic": row["synthetic"],
    } for row in records]
    pd.DataFrame(flat).to_csv(csv_path, index=False, lineterminator="\n")
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    manifest = {
        "dataset_name": "G4F-WM-006-synthetic-event-state-transitions",
        "dataset_version": config["dataset_version"], "generator_version": config["generator_version"],
        "synthetic": True, "seed": config["seed"], "config_sha256": config_hash,
        "runtime_versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "row_count": len(records),
        "path_counts": {path: sum(1 for row in records if row["path_type"] == path) for path in sorted(PATH_TYPES)},
        "event_counts": {kind: sum(1 for row in records if row["event"]["event_type"] == kind) for kind in sorted(EVENT_TYPES)},
        "output_sha256": {
            trajectories_path.name: hashlib.sha256(trajectories_path.read_bytes()).hexdigest(),
            csv_path.name: hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(write_dataset(args.config, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
