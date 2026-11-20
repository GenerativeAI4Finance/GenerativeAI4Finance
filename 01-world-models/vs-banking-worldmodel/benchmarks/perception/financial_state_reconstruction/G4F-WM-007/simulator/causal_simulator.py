"""Paired potential-outcome simulation with explicit, configurable rules."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "causal_scenarios.json"
DEFAULT_OUTPUT = ROOT / "data" / "sample"
POLICY_FIELDS = {"interest_rate_pct", "term_months", "credit_limit_usd", "collections_delay_days"}
ARM_KINDS = {"control", "interest_rate", "repayment_term", "credit_limit", "collections_timing"}


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("entity_count", 0) < 1 or config.get("horizon_months", 0) < 1:
        raise ValueError("entity_count and horizon_months must be positive")
    arms = config.get("intervention_arms", [])
    arm_ids = [arm.get("arm_id") for arm in arms]
    if len(arm_ids) != len(set(arm_ids)) or not arms:
        raise ValueError("intervention arm IDs must be unique and at least one arm is required")
    if not any(arm.get("kind") == "control" for arm in arms):
        raise ValueError("a control arm is required")
    for arm in arms:
        if arm.get("kind") not in ARM_KINDS:
            raise ValueError(f"unsupported intervention kind: {arm.get('kind')}")
    return config


def generate_cohort(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[float]]:
    """Generate observed covariates, risk-assigned baseline policies and shared shocks."""
    rng = np.random.default_rng(config["seed"])
    ranges = config["baseline_generation"]
    features_rows: list[dict[str, Any]] = []
    policy_rows: list[dict[str, Any]] = []
    shared_shocks: list[float] = []
    for index in range(config["entity_count"]):
        entity_id = f"SYN-WM007-{index + 1:04d}"
        income = round(float(rng.uniform(*ranges["monthly_income_usd"])), 2)
        volatility = round(float(rng.uniform(*ranges["income_volatility"])), 6)
        balance_months = round(float(rng.uniform(*ranges["balance_to_income_months"])), 6)
        balance = round(income * balance_months, 2)
        risk_index = float(np.clip(0.55 * balance_months / 5 + 0.45 * volatility / 0.35, 0, 1))
        features_rows.append({
            "entity_id": entity_id,
            "monthly_income_usd": income,
            "income_volatility": volatility,
            "balance_usd": balance,
            "balance_to_income_months": balance_months,
            "risk_index": round(risk_index, 6),
            "synthetic": True,
        })
        risk = features_rows[-1]["risk_index"]
        policy_rows.append({
            "entity_id": entity_id,
            "interest_rate_pct": round(5 + 15 * risk, 6),
            "term_months": 24 if risk >= 0.65 else 36,
            "credit_limit_usd": round(balance * (1.1 + 0.9 * (1 - risk)), 2),
            "collections_delay_days": 15 if risk >= 0.65 else 30,
        })
        shared_shocks.append(float(rng.uniform(0, 1)))
    return features_rows, policy_rows, shared_shocks


def apply_intervention(baseline: dict[str, Any], arm: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Return effective policy variables after exactly the configured intervention."""
    policy = {key: baseline[key] for key in POLICY_FIELDS}
    change = arm.get("change", {})
    kind = arm["kind"]
    model = config["structural_model"]
    if kind == "control":
        if change:
            raise ValueError("control arm must not define an intervention change")
    elif kind == "interest_rate":
        policy["interest_rate_pct"] += change["delta_pct_points"]
        policy["interest_rate_pct"] = max(model["minimum_interest_rate_pct"], policy["interest_rate_pct"])
    elif kind == "repayment_term":
        policy["term_months"] += change["delta_months"]
        policy["term_months"] = min(model["maximum_term_months"], max(model["minimum_term_months"], policy["term_months"]))
    elif kind == "credit_limit":
        old_limit = policy["credit_limit_usd"]
        policy["credit_limit_usd"] *= change["multiplier"]
        if policy["credit_limit_usd"] < old_limit:
            raise ValueError("this simulator currently supports non-decreasing credit-limit interventions")
    elif kind == "collections_timing":
        policy["collections_delay_days"] += change["delta_days"]
        if policy["collections_delay_days"] < 0:
            raise ValueError("collections delay cannot be negative")
    if not 0 <= policy["interest_rate_pct"] <= model["maximum_interest_rate_pct"]:
        raise ValueError("intervened interest rate is outside configured bounds")
    if policy["term_months"] < 1:
        raise ValueError("intervened repayment term must be positive")
    return policy


def _monthly_payment(balance: float, rate_pct: float, term_months: int) -> float:
    monthly_rate = rate_pct / 1200
    if monthly_rate == 0:
        return balance / term_months
    return balance * monthly_rate / (1 - (1 + monthly_rate) ** (-term_months))


def simulate_outcome(
    features: dict[str, Any], baseline_policy: dict[str, Any], intervention_policy: dict[str, Any],
    arm: dict[str, Any], shared_shock: float, config: dict[str, Any],
) -> dict[str, Any]:
    """Calculate a structural-model outcome for a single potential-outcome arm."""
    model = config["structural_model"]
    balance = features["balance_usd"]
    if arm["kind"] == "credit_limit":
        added_limit = max(0.0, intervention_policy["credit_limit_usd"] - baseline_policy["credit_limit_usd"])
        balance += added_limit * model["credit_limit_take_up_share"]
    payment = _monthly_payment(balance, intervention_policy["interest_rate_pct"], intervention_policy["term_months"])
    income = features["monthly_income_usd"]
    volatility = features["income_volatility"]
    expense_share = model["monthly_expense_share_base"] + model["volatility_expense_sensitivity"] * volatility
    net_cashflow = income * (1 - expense_share) - payment
    payment_burden = payment / income
    balance_to_income = balance / income
    linear_risk = (
        model["stress_intercept"]
        + model["payment_burden_coefficient"] * payment_burden
        + model["balance_to_income_coefficient"] * balance_to_income
        + model["income_volatility_coefficient"] * volatility
        + model["collections_delay_coefficient_per_day_after_15"]
        * max(0, intervention_policy["collections_delay_days"] - model["collections_delay_reference_days"])
    )
    monthly_hazard = float(1 / (1 + np.exp(-linear_risk)))
    horizon_months = config["horizon_months"]
    default_probability = float(1 - (1 - monthly_hazard) ** horizon_months)
    return {
        "monthly_payment_usd": round(float(payment), 2),
        "projected_net_cashflow_usd": round(float(net_cashflow), 2),
        "modeled_default_probability": round(default_probability, 8),
        "simulated_default_within_horizon": bool(shared_shock < default_probability),
    }


def simulate(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    features_rows, policy_rows, shocks = generate_cohort(config)
    records: list[dict[str, Any]] = []
    for features, baseline, shock in zip(features_rows, policy_rows, shocks):
        for arm in config["intervention_arms"]:
            effective_policy = apply_intervention(baseline, arm, config)
            outcomes = simulate_outcome(features, baseline, effective_policy, arm, shock, config)
            baseline_values = {key: baseline[key] for key in POLICY_FIELDS}
            records.append({
                "schema_version": "1.0.0",
                "dataset_version": config["dataset_version"],
                "entity_id": features["entity_id"],
                "arm_id": arm["arm_id"],
                "horizon_months": config["horizon_months"],
                "observational_features": {key: value for key, value in features.items() if key not in {"entity_id", "synthetic"}},
                "baseline_policy": baseline_values,
                "intervention": {**effective_policy, "intervention_kind": arm["kind"], "change": arm.get("change", {})},
                "simulation_context": {"shared_exogenous_shock": round(shock, 12)},
                "outcomes": outcomes,
                "synthetic": True,
            })
    effects = summarize_effects(records, config)
    return features_rows, policy_rows, records, effects


def summarize_effects(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    control_arm = next(arm["arm_id"] for arm in config["intervention_arms"] if arm["kind"] == "control")
    by_entity_arm = {(row["entity_id"], row["arm_id"]): row for row in records}
    arms = [arm["arm_id"] for arm in config["intervention_arms"] if arm["arm_id"] != control_arm]
    summary: list[dict[str, Any]] = []
    for arm_id in arms:
        pairs = [(by_entity_arm[(entity_id, arm_id)], by_entity_arm[(entity_id, control_arm)])
                 for entity_id in sorted({row["entity_id"] for row in records})]
        for outcome in ("modeled_default_probability", "simulated_default_within_horizon", "projected_net_cashflow_usd", "monthly_payment_usd"):
            treatment_values = [float(treatment["outcomes"][outcome]) for treatment, _ in pairs]
            control_values = [float(control["outcomes"][outcome]) for _, control in pairs]
            differences = [treated - base for treated, base in zip(treatment_values, control_values)]
            summary.append({
                "arm_id": arm_id,
                "control_arm_id": control_arm,
                "outcome": outcome,
                "estimand_label": "paired_within_simulator_mean_difference",
                "control_mean": round(float(np.mean(control_values)), 8),
                "intervention_mean": round(float(np.mean(treatment_values)), 8),
                "paired_mean_difference": round(float(np.mean(differences)), 8),
                "paired_unit_count": len(pairs),
                "interpretation_limit": "Effect implied by this configured synthetic structural model only; not an empirical causal estimate.",
            })
    return summary


def write_dataset(config_path: Path = DEFAULT_CONFIG, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    config = load_config(config_path)
    features, policies, records, effects = simulate(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "observational_features.csv": pd.DataFrame(features),
        "baseline_policies.csv": pd.DataFrame(policies),
        "potential_outcomes.csv": pd.DataFrame([{
            "entity_id": row["entity_id"], "arm_id": row["arm_id"], "horizon_months": row["horizon_months"],
            "intervention_kind": row["intervention"]["intervention_kind"],
            **{key: row["intervention"][key] for key in POLICY_FIELDS},
            "intervention_change_json": json.dumps(row["intervention"]["change"], sort_keys=True),
            **row["simulation_context"], **row["outcomes"], "synthetic": row["synthetic"],
        } for row in records]),
    }
    hashes = {}
    for name, frame in outputs.items():
        path = output_dir / name
        frame.to_csv(path, index=False, lineterminator="\n")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    json_path = output_dir / "example_potential_outcomes.json"
    json_path.write_text(json.dumps(records[: min(15, len(records))], indent=2) + "\n", encoding="utf-8")
    hashes[json_path.name] = hashlib.sha256(json_path.read_bytes()).hexdigest()
    summary_path = output_dir / "model_implied_effects.json"
    summary_path.write_text(json.dumps(effects, indent=2) + "\n", encoding="utf-8")
    hashes[summary_path.name] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    manifest = {
        "dataset_name": "G4F-WM-007-synthetic-causal-intervention-scenarios",
        "dataset_version": config["dataset_version"], "simulator_version": config["simulator_version"],
        "synthetic": True, "seed": config["seed"],
        "runtime_versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "entity_count": len(features), "intervention_arm_count": len(config["intervention_arms"]),
        "potential_outcome_record_count": len(records), "outcome_summary_count": len(effects),
        "output_sha256": hashes,
        "estimand_note": "Paired differences are simulator-implied counterfactual contrasts, not empirical causal effects.",
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
