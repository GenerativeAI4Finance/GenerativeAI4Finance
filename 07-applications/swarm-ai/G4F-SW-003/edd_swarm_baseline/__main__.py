"""Command-line runner for the deterministic EDD swarm baseline."""

import argparse
import json
from pathlib import Path

from .workflow import available_scenarios, load_json, run_scenario


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic synthetic EDD swarm scenario.")
    parser.add_argument("--scenario", help="G4F-SW-002 scenario ID or JSON file path")
    parser.add_argument("--config", help="Workflow configuration JSON path")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--list-scenarios", action="store_true", help="List bundled scenario IDs")
    args = parser.parse_args()

    available = available_scenarios()
    if args.list_scenarios:
        for scenario_id in available:
            print(scenario_id)
        return 0

    scenario_value = args.scenario or "G4F-SW-002-001"
    scenario_path = available.get(scenario_value, Path(scenario_value))
    config = load_json(args.config) if args.config else None
    result = run_scenario(load_json(scenario_path), config=config)
    output_path = Path(args.output) if args.output else Path(__file__).resolve().parents[1] / "examples" / "example_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
