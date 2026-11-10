"""Create deterministic fictional borrower, loan, state, and repayment data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "generator.json"
DEFAULT_OUTPUT = ROOT / "data" / "sample"
PATH_NAMES = ("normal_repayment", "liquidity_stress", "delinquency", "cure", "default")


def _load_config(config: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if config is None:
        config_path = DEFAULT_CONFIG
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    elif isinstance(config, dict):
        loaded = config
    else:
        loaded = json.loads(Path(config).read_text(encoding="utf-8"))
    _validate_config(loaded)
    return loaded


def _validate_config(config: dict[str, Any]) -> None:
    required = {
        "dataset_version", "generator_version", "seed", "start_date", "observation_months", "term_months",
        "default_after_days_past_due", "borrower_count_by_path", "assumptions",
    }
    missing = required - config.keys()
    if missing:
        raise ValueError(f"Configuration is missing required keys: {sorted(missing)}")
    if config["observation_months"] < 1 or config["term_months"] < config["observation_months"]:
        raise ValueError("term_months must be at least observation_months, and both must be positive.")
    if config["default_after_days_past_due"] < 1:
        raise ValueError("default_after_days_past_due must be positive.")
    counts = config["borrower_count_by_path"]
    if set(counts) != set(PATH_NAMES) or any(not isinstance(count, int) or count < 1 for count in counts.values()):
        raise ValueError(f"borrower_count_by_path must specify a positive integer count for {PATH_NAMES}.")
    assumptions = config["assumptions"]
    if not 0 < assumptions["liquidity_stress_income_multiplier"] <= 1:
        raise ValueError("liquidity_stress_income_multiplier must be in (0, 1].")
    month_indices = [
        *assumptions["stress_month_indices"],
        *assumptions["delinquency_missed_month_indices"],
        *assumptions["cure_missed_month_indices"],
        assumptions["cure_month_index"],
        *assumptions["default_missed_month_indices"],
    ]
    if any(index < 0 or index >= config["observation_months"] for index in month_indices):
        raise ValueError("All configured scenario month indices must be inside the observation window.")


def _money(value: float) -> float:
    return round(float(value), 2)


def _scheduled_payment(principal: float, annual_rate: float, term_months: int) -> float:
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return _money(principal / term_months)
    return _money(principal * monthly_rate / (1 - (1 + monthly_rate) ** (-term_months)))


def _path_schedule(path: str, month: int, assumptions: dict[str, Any]) -> tuple[bool, bool, bool]:
    """Return (miss, stress, cure-payment) flags for a scenario month."""
    if path == "normal_repayment":
        return False, False, False
    if path == "liquidity_stress":
        return False, month in assumptions["stress_month_indices"], False
    if path == "delinquency":
        return month in assumptions["delinquency_missed_month_indices"], False, False
    if path == "cure":
        return month in assumptions["cure_missed_month_indices"], False, month == assumptions["cure_month_index"]
    if path == "default":
        return month in assumptions["default_missed_month_indices"], False, False
    raise ValueError(f"Unknown scenario path: {path}")


def generate_dataset(config: dict[str, Any] | str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Generate reproducible tables using a fixed NumPy random generator seed."""
    cfg = _load_config(config)
    assumptions = cfg["assumptions"]
    rng = np.random.default_rng(cfg["seed"])
    start_date = pd.Timestamp(cfg["start_date"])
    start_date = start_date.tz_localize("UTC") if start_date.tzinfo is None else start_date.tz_convert("UTC")
    borrowers: list[dict[str, Any]] = []
    loans: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    repayments: list[dict[str, Any]] = []

    paths = [path for path in PATH_NAMES for _ in range(cfg["borrower_count_by_path"][path])]
    for index, path in enumerate(paths, start=1):
        borrower_id = f"SYN-BOR-{index:04d}"
        loan_id = f"SYN-LOAN-{index:04d}"
        borrower_type = "individual" if index % 2 else "small_business"
        annual_income = _money(rng.uniform(*assumptions["annual_income_usd_range"]))
        monthly_income = _money(annual_income / 12)
        expense_share = float(rng.uniform(*assumptions["monthly_expense_share_range"]))
        monthly_expenses = _money(monthly_income * expense_share)
        principal = _money(rng.uniform(*assumptions["loan_principal_usd_range"]))
        annual_rate = round(float(rng.uniform(*assumptions["annual_interest_rate_range"])), 5)
        payment_due = _scheduled_payment(principal, annual_rate, cfg["term_months"])
        borrowers.append({
            "borrower_id": borrower_id,
            "borrower_type": borrower_type,
            "annual_income_usd": annual_income,
            "home_region_code": f"SYN-R{(index % 5) + 1:02d}",
            "synthetic": True,
        })
        loans.append({
            "loan_id": loan_id,
            "borrower_id": borrower_id,
            "origination_date": (start_date - pd.DateOffset(months=1)).date().isoformat(),
            "original_principal_usd": principal,
            "annual_interest_rate": annual_rate,
            "term_months": cfg["term_months"],
            "scheduled_payment_usd": payment_due,
            "scenario_path": path,
            "synthetic": True,
        })

        balance = principal
        overdue_dates: list[pd.Timestamp] = []
        loan_defaulted = False
        stress_factor = assumptions["liquidity_stress_income_multiplier"]
        for month in range(cfg["observation_months"]):
            due_date = start_date + pd.DateOffset(months=month)
            due_date = due_date.tz_localize("UTC") if due_date.tzinfo is None else due_date.tz_convert("UTC")
            miss, stressed, cure_payment = _path_schedule(path, month, assumptions)
            current_income = _money(monthly_income * (stress_factor if stressed else 1.0))
            net_cash_flow = _money(current_income - monthly_expenses)
            beginning_balance = balance
            interest_accrued = _money(beginning_balance * annual_rate / 12) if not loan_defaulted else 0.0
            balance = _money(balance + interest_accrued)
            cure_occurred = False
            if loan_defaulted:
                payment_status = "not_due_after_default"
                payment_amount = 0.0
                total_payment_amount = 0.0
                event_type = "default"
                action_taken = "none"
            elif miss:
                overdue_dates.append(due_date)
                payment_status = "missed"
                payment_amount = 0.0
                total_payment_amount = 0.0
                event_type = "delinquency"
                action_taken = "none"
            else:
                cure_occurred = cure_payment and bool(overdue_dates)
                total_payment_amount = _money(payment_due * (len(overdue_dates) + 1)) if cure_occurred else payment_due
                payment_amount = payment_due
                payment_status = "paid"
                if cure_occurred:
                    for prior in repayments:
                        if prior["loan_id"] == loan_id and prior["payment_status"] == "missed":
                            prior_due_date = pd.Timestamp(prior["due_date"], tz="UTC")
                            prior["payment_status"] = "paid_late"
                            prior["payment_date"] = due_date.date().isoformat()
                            prior["payment_amount_usd"] = payment_due
                            prior["days_past_due_at_observation"] = (due_date - prior_due_date).days
                    overdue_dates.clear()
                elif due_date in overdue_dates:
                    overdue_dates.remove(due_date)
                principal_paid = min(balance, max(0.0, total_payment_amount - interest_accrued))
                balance = _money(max(0.0, balance - principal_paid))
                event_type = "cure" if cure_occurred else "payment"
                action_taken = "cure_payment" if cure_occurred else "payment_received"

            days_past_due = max(0, (due_date - min(overdue_dates)).days) if overdue_dates else 0
            if not loan_defaulted and days_past_due >= cfg["default_after_days_past_due"]:
                loan_defaulted = True
                payment_status = "defaulted"
                payment_amount = 0.0
                event_type = "default"
                action_taken = "loan_charged_off"
            elif loan_defaulted:
                event_type = "default"
            if loan_defaulted:
                state = "default"
            elif cure_occurred:
                state = "cured"
            elif days_past_due > 0:
                state = "delinquent"
            elif stressed:
                state = "liquidity_stress"
            else:
                state = "current"

            repayments.append({
                "repayment_id": f"SYN-PMT-{index:04d}-{month + 1:02d}",
                "loan_id": loan_id,
                "due_date": due_date.date().isoformat(),
                "payment_date": due_date.date().isoformat() if payment_amount > 0 else None,
                "scheduled_payment_usd": 0.0 if payment_status == "not_due_after_default" else payment_due,
                "payment_amount_usd": payment_amount,
                "payment_status": payment_status,
                "days_past_due_at_observation": days_past_due,
                "synthetic": True,
            })
            states.append({
                "state_id": f"SYN-STATE-{index:04d}-{month + 1:02d}",
                "borrower_id": borrower_id,
                "loan_id": loan_id,
                "state_date": due_date.date().isoformat(),
                "month_index": month,
                "scenario_path": path,
                "financial_state": state,
                "event_type": event_type,
                "action_taken": action_taken,
                "outstanding_balance_usd": balance,
                "monthly_income_usd": current_income,
                "monthly_expenses_usd": monthly_expenses,
                "net_cash_flow_usd": net_cash_flow,
                "days_past_due": days_past_due,
                "synthetic": True,
            })

    return {
        "borrowers": pd.DataFrame(borrowers),
        "loans": pd.DataFrame(loans),
        "monthly_states": pd.DataFrame(states),
        "repayment_history": pd.DataFrame(repayments),
    }


def write_dataset(
    dataset: dict[str, pd.DataFrame],
    output_dir: str | Path = DEFAULT_OUTPUT,
    config: dict[str, Any] | str | Path | None = None,
) -> Path:
    """Write stable CSVs plus a manifest with the seed and configuration hash."""
    cfg = _load_config(config)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    file_hashes = {}
    for name, frame in dataset.items():
        csv_path = destination / f"{name}.csv"
        frame.to_csv(csv_path, index=False, lineterminator="\n", float_format="%.2f")
        file_hashes[csv_path.name] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    config_bytes = json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest = {
        "dataset_name": "G4F-WM-002-synthetic-borrower-loan-states",
        "dataset_version": cfg["dataset_version"],
        "generator_version": cfg["generator_version"],
        "synthetic": True,
        "seed": cfg["seed"],
        "runtime_versions": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__},
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "output_sha256": file_hashes,
        "row_counts": {name: int(len(frame)) for name, frame in dataset.items()},
        "scenario_counts": {str(k): int(v) for k, v in dataset["loans"]["scenario_path"].value_counts().sort_index().items()},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    config = _load_config(args.config)
    data = generate_dataset(config)
    validate_dataset(data, config)
    destination = write_dataset(data, args.output_dir, config)
    print(f"Wrote synthetic dataset to {destination}")


def validate_dataset(dataset: dict[str, pd.DataFrame], config: dict[str, Any] | str | Path | None = None) -> None:
    """Raise ValueError when generated tables violate key referential/time/value constraints."""
    cfg = _load_config(config)
    borrowers, loans, states, repayments = (dataset[name] for name in ("borrowers", "loans", "monthly_states", "repayment_history"))
    if not borrowers["borrower_id"].is_unique or not loans["loan_id"].is_unique:
        raise ValueError("Borrower and loan IDs must be unique.")
    if not set(loans["borrower_id"]) <= set(borrowers["borrower_id"]):
        raise ValueError("Every loan must reference an existing borrower.")
    if set(states["loan_id"]) != set(loans["loan_id"]) or set(repayments["loan_id"]) != set(loans["loan_id"]):
        raise ValueError("Each loan must have state and repayment records.")
    date_columns = [(states, "state_date"), (repayments, "due_date"), (loans, "origination_date")]
    for frame, column in date_columns:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        if parsed.isna().any():
            raise ValueError(f"Invalid dates in {column}.")
    state_dates = pd.to_datetime(states["state_date"])
    if (states.assign(_state_date=state_dates).sort_values(["loan_id", "month_index"]).groupby("loan_id")["_state_date"].diff().dropna() <= pd.Timedelta(0)).any():
        raise ValueError("State dates must increase within each loan.")
    payment_dates = pd.to_datetime(repayments["payment_date"], errors="coerce")
    due_dates = pd.to_datetime(repayments["due_date"])
    has_payment_date = payment_dates.notna()
    if (payment_dates[has_payment_date] < due_dates[has_payment_date]).any():
        raise ValueError("A payment date cannot precede its due date.")
    scheduled_amounts = repayments.merge(loans[["loan_id", "scheduled_payment_usd"]], on="loan_id", suffixes=("_history", "_loan"))
    if (scheduled_amounts["payment_amount_usd"] > scheduled_amounts["scheduled_payment_usd_loan"] + 0.01).any():
        raise ValueError("An installment payment cannot exceed its scheduled amount in this installment-level dataset.")
    if (loans["original_principal_usd"] <= 0).any() or (loans["scheduled_payment_usd"] <= 0).any():
        raise ValueError("Loan principal and scheduled installments must be positive.")
    if (states["outstanding_balance_usd"] < 0).any() or (repayments["payment_amount_usd"] < 0).any():
        raise ValueError("Balances and payment amounts must not be negative.")
    if ((states["days_past_due"] < 0) | (states["days_past_due"] > 3650)).any():
        raise ValueError("Days past due is outside the supported range.")
    if not borrowers["synthetic"].all() or not loans["synthetic"].all() or not states["synthetic"].all() or not repayments["synthetic"].all():
        raise ValueError("Every generated row must be explicitly marked synthetic.")
    if ((repayments["payment_status"] == "missed") & repayments["payment_date"].notna()).any():
        raise ValueError("Missed installments cannot have a payment date.")
    defaulted = states[states["financial_state"] == "default"]
    if not defaulted.empty and (defaulted["days_past_due"] < cfg["default_after_days_past_due"]).any():
        raise ValueError("Default state begins before the configured delinquency threshold.")


if __name__ == "__main__":
    main()
