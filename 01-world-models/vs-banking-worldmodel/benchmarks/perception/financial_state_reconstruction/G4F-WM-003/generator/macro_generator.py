"""Generate reproducible fictional macro and sector stress sequences."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "scenarios.json"
DEFAULT_OUTPUT = ROOT / "data" / "sample"


def _load_config(config: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if config is None:
        loaded = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    elif isinstance(config, dict):
        loaded = config
    else:
        loaded = json.loads(Path(config).read_text(encoding="utf-8"))
    _validate_config(loaded)
    return loaded


def _validate_config(config: dict[str, Any]) -> None:
    required = {"dataset_version", "generator_version", "seed", "start_month", "periods", "base_policy_rate_pct", "synthetic_businesses_per_sector", "scenarios", "sectors", "assumptions"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"Configuration is missing keys: {sorted(missing)}")
    if not isinstance(config["seed"], int) or config["periods"] < 2 or config["synthetic_businesses_per_sector"] < 1:
        raise ValueError("Seed must be an integer; periods must be >= 2 and business count must be positive.")
    if set(config["scenarios"]) != {"baseline", "stress"}:
        raise ValueError("Configuration must define baseline and stress scenarios.")
    if not config["sectors"]:
        raise ValueError("At least one sector definition is required.")
    try:
        pd.Period(config["start_month"], freq="M")
    except (TypeError, ValueError) as exc:
        raise ValueError("start_month must be a valid YYYY-MM date.") from exc
    for name, scenario in config["scenarios"].items():
        shock_month = scenario["shock_start_month_index"]
        if shock_month is not None and not 0 <= shock_month < config["periods"]:
            raise ValueError(f"Scenario {name} shock_start_month_index must be inside the sequence.")
        if set(scenario["demand_change_pct_by_sector"]) != set(config["sectors"]):
            raise ValueError(f"Scenario {name} must define demand changes for every configured sector.")
    for sector, values in config["sectors"].items():
        for key in ("commodity_revenue_sensitivity", "commodity_cost_sensitivity", "rate_sensitivity"):
            if values[key] < 0:
                raise ValueError(f"{sector}.{key} must be non-negative.")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def generate_dataset(config: dict[str, Any] | str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Create sequences and assumption-linked business outcomes with a fixed seed."""
    cfg = _load_config(config)
    assumptions = cfg["assumptions"]
    rng = np.random.default_rng(cfg["seed"])
    dates = pd.date_range(pd.Period(cfg["start_month"], freq="M").start_time, periods=cfg["periods"], freq="ME")

    base_rates = [float(cfg["base_policy_rate_pct"])]
    base_commodity = [float(assumptions["initial_commodity_price_index"])]
    aggregate_demand = [float(assumptions["initial_sector_demand_index"])]
    for _ in range(1, cfg["periods"]):
        base_rates.append(max(0.25, base_rates[-1] + rng.normal(0, assumptions["monthly_rate_noise_std_pct_points"])))
        base_commodity.append(max(1.0, base_commodity[-1] * (1 + rng.normal(0, assumptions["monthly_commodity_noise_std_pct"]))))
        aggregate_demand.append(max(25.0, aggregate_demand[-1] * (1 + rng.normal(0, assumptions["monthly_demand_noise_std_pct"]))))

    baseline_sector_demand: dict[str, list[float]] = {}
    for sector in cfg["sectors"]:
        sector_noise = rng.normal(0, assumptions["monthly_demand_noise_std_pct"] / 2, cfg["periods"])
        baseline_sector_demand[sector] = [
            max(25.0, aggregate_demand[index] * (1 + sector_noise[index]))
            for index in range(cfg["periods"])
        ]

    macro_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    businesses: list[dict[str, Any]] = []
    outcome_rows: list[dict[str, Any]] = []
    business_parameters: dict[str, dict[str, float | str]] = {}
    for sector, coefficients in cfg["sectors"].items():
        for sequence in range(1, cfg["synthetic_businesses_per_sector"] + 1):
            business_id = f"SYN-BIZ-{sector[:3].upper()}-{sequence:03d}"
            business_parameters[business_id] = {
                "sector": sector,
                "base_revenue_index": round(float(rng.uniform(*assumptions["business_revenue_index_range"])), 6),
                "operating_cost_share": round(float(rng.uniform(*assumptions["operating_cost_share_range"])), 6),
                "baseline_debt_service_share": round(float(rng.uniform(*assumptions["baseline_debt_service_share_range"])), 6),
            }
            businesses.append({"business_id": business_id, "sector": sector, "synthetic": True})

    baseline_cashflow: dict[tuple[str, str], float] = {}
    for scenario_name, scenario in cfg["scenarios"].items():
        shock_start = scenario["shock_start_month_index"]
        for sector, coefficients in cfg["sectors"].items():
            sector_demand_delta = scenario["demand_change_pct_by_sector"][sector]
            for month_index, date in enumerate(dates):
                active = shock_start is not None and month_index >= shock_start
                rate = base_rates[month_index] + (scenario["policy_rate_increase_pct_points"] if active else 0.0)
                commodity = base_commodity[month_index] * (1 + scenario["commodity_price_increase_pct"] if active else 1.0)
                agg_delta = scenario.get("aggregate_demand_change_pct", 0.0)
                aggregate = aggregate_demand[month_index] * (1 + agg_delta if active else 1.0)
                sector_demand = baseline_sector_demand[sector][month_index] * (1 + sector_demand_delta if active else 1.0)
                sector_demand = max(1.0, sector_demand)
                shock_event = "none"
                if active:
                    shock_event = coefficients["event_name"]
                macro_rows.append({
                    "scenario": scenario_name,
                    "date": date.date().isoformat(),
                    "month_index": month_index,
                    "sector": sector,
                    "policy_rate_pct": round(rate, 6),
                    "commodity_price_index": round(commodity, 6),
                    "aggregate_demand_index": round(aggregate, 6),
                    "sector_demand_index": round(sector_demand, 6),
                    "sector_event": shock_event,
                    "relationship_type": "simulation_assumption",
                    "synthetic": True,
                })
                if active and month_index == shock_start:
                    event_rows.append({
                        "event_id": f"SYN-EVT-{scenario_name.upper()}-{sector.upper()}-{month_index:03d}",
                        "scenario": scenario_name,
                        "date": date.date().isoformat(),
                        "sector": sector,
                        "event_name": coefficients["event_name"],
                        "policy_rate_change_pct_points": scenario["policy_rate_increase_pct_points"],
                        "commodity_price_change_pct": scenario["commodity_price_increase_pct"] * 100,
                        "sector_demand_change_pct": sector_demand_delta * 100,
                        "relationship_type": "simulation_assumption",
                        "synthetic": True,
                    })
                for business_id, params in business_parameters.items():
                    if params["sector"] != sector:
                        continue
                    commodity_change = commodity / assumptions["initial_commodity_price_index"] - 1
                    revenue = float(params["base_revenue_index"]) * sector_demand / 100 * (1 + coefficients["commodity_revenue_sensitivity"] * commodity_change)
                    operating_costs = float(params["base_revenue_index"]) * float(params["operating_cost_share"]) * sector_demand / 100 * (1 + coefficients["commodity_cost_sensitivity"] * commodity_change)
                    debt_service = float(params["base_revenue_index"]) * float(params["baseline_debt_service_share"]) * (rate / cfg["base_policy_rate_pct"]) ** coefficients["rate_sensitivity"]
                    cashflow = revenue - operating_costs - debt_service
                    if scenario_name == "baseline":
                        baseline_cashflow[(business_id, date.date().isoformat())] = cashflow
                    base_cf = baseline_cashflow.get((business_id, date.date().isoformat()))
                    if base_cf is None:
                        raise ValueError("Baseline sequence must be evaluated before stress outcomes.")
                    outcome_rows.append({
                        "business_id": business_id,
                        "scenario": scenario_name,
                        "date": date.date().isoformat(),
                        "month_index": month_index,
                        "sector": sector,
                        "revenue_index": round(revenue, 6),
                        "operating_cost_index": round(operating_costs, 6),
                        "debt_service_index": round(debt_service, 6),
                        "modeled_cashflow_index": round(cashflow, 6),
                        "cashflow_change_vs_baseline_index": round(cashflow - base_cf, 6),
                        "cashflow_stress_flag": cashflow <= assumptions["cashflow_stress_threshold_index"],
                        "relationship_type": "simulation_assumption",
                        "synthetic": True,
                    })

    dataset = {
        "businesses": pd.DataFrame(businesses),
        "macro_sequences": pd.DataFrame(macro_rows),
        "sector_events": pd.DataFrame(event_rows),
        "business_outcomes": pd.DataFrame(outcome_rows),
    }
    validate_dataset(dataset, cfg)
    return dataset


def validate_dataset(dataset: dict[str, pd.DataFrame], config: dict[str, Any] | str | Path | None = None) -> None:
    """Check dimensions, dates, assumptions labels, and key scenario constraints."""
    cfg = _load_config(config)
    businesses = dataset["businesses"]
    macro = dataset["macro_sequences"]
    events = dataset["sector_events"]
    outcomes = dataset["business_outcomes"]
    if not businesses["business_id"].is_unique:
        raise ValueError("business_id values must be unique.")
    for name, frame in dataset.items():
        if not frame["synthetic"].all():
            raise ValueError(f"All rows in {name} must be marked synthetic.")
        if name in {"macro_sequences", "sector_events", "business_outcomes"} and not (frame["relationship_type"] == "simulation_assumption").all():
            raise ValueError(f"Rows in {name} must identify relationships as simulation assumptions.")
        if "date" in frame and pd.to_datetime(frame["date"], errors="coerce").isna().any():
            raise ValueError(f"Invalid date in {name}.")
    scenarios = set(cfg["scenarios"])
    sectors = set(cfg["sectors"])
    if set(macro["scenario"]) != scenarios or set(macro["sector"]) != sectors:
        raise ValueError("Macro rows must cover every configured scenario and sector.")
    expected_macro_rows = len(scenarios) * len(sectors) * cfg["periods"]
    if len(macro) != expected_macro_rows:
        raise ValueError("Macro sequence has an unexpected row count.")
    macro_groups = macro.groupby(["scenario", "sector"], sort=False)
    if any(len(group) != cfg["periods"] or not group["month_index"].is_monotonic_increasing for _, group in macro_groups):
        raise ValueError("Each scenario/sector sequence must contain ordered monthly observations.")
    numeric_macro = ["policy_rate_pct", "commodity_price_index", "aggregate_demand_index", "sector_demand_index"]
    if (macro[numeric_macro] <= 0).any().any():
        raise ValueError("Rates and macro/sector indices must be positive.")
    if set(outcomes["business_id"]) != set(businesses["business_id"]):
        raise ValueError("Business outcomes must reference known synthetic businesses.")
    expected_outcome_rows = len(businesses) * len(scenarios) * cfg["periods"]
    if len(outcomes) != expected_outcome_rows:
        raise ValueError("Business outcome sequence has an unexpected row count.")
    if outcomes.duplicated(["business_id", "scenario", "date"]).any():
        raise ValueError("Business outcome rows must be unique by business, scenario, and date.")
    if (outcomes[["revenue_index", "operating_cost_index", "debt_service_index"]] < 0).any().any():
        raise ValueError("Revenue, operating cost, and debt service indices cannot be negative.")
    if set(events["scenario"]) != {"stress"}:
        raise ValueError("The configured example has stress events only; baseline must have no discrete events.")


def write_dataset(dataset: dict[str, pd.DataFrame], output_dir: str | Path = DEFAULT_OUTPUT, config: dict[str, Any] | str | Path | None = None) -> Path:
    """Write stable CSVs and a manifest with configuration/runtime provenance."""
    cfg = _load_config(config)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, frame in dataset.items():
        path = destination / f"{name}.csv"
        frame.to_csv(path, index=False, lineterminator="\n", float_format="%.6f")
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "dataset_name": "G4F-WM-003-synthetic-macro-sector-sequences",
        "dataset_version": cfg["dataset_version"],
        "generator_version": cfg["generator_version"],
        "synthetic": True,
        "seed": cfg["seed"],
        "runtime_versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
        "config_sha256": hashlib.sha256(_canonical_json(cfg)).hexdigest(),
        "output_sha256": hashes,
        "row_counts": {name: int(len(frame)) for name, frame in dataset.items()},
        "scenario_counts": {str(k): int(v) for k, v in dataset["macro_sequences"].groupby("scenario").size().items()},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    cfg = _load_config(args.config)
    dataset = generate_dataset(cfg)
    destination = write_dataset(dataset, args.output_dir, cfg)
    print(f"Wrote synthetic scenario data to {destination}")


if __name__ == "__main__":
    main()
