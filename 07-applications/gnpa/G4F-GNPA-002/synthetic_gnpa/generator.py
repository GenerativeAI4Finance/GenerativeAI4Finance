"""Generate deterministic, wholly fictional borrower/account histories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DATASET_VERSION = "1.0.0"
DEFAULT_SEED = 20261120
HISTORY_COLUMNS = [
    "dataset_version",
    "is_synthetic",
    "bank_id",
    "borrower_id",
    "account_id",
    "snapshot_date",
    "days_past_due",
    "overdue_amount_inr",
    "outstanding_balance_inr",
    "repayment_ratio_30d",
    "credit_utilization",
    "cashflow_stress_score",
    "synthetic_stress_event",
    "synthetic_cure_event",
    "synthetic_asset_status",
    "npa_entry_event",
    "observation_coverage_end",
]


def generate_synthetic_history(
    n_borrowers: int = 400,
    seed: int = DEFAULT_SEED,
    start_date: str = "2025-01-01",
    n_snapshots: int = 16,
) -> pd.DataFrame:
    """Return fictional monthly account states; repeated calls with same args match.

    The NPA status is a simulation proxy (DPD > 90), not a regulatory classifier.
    A single funded account is generated per borrower so account and borrower-level
    status coincide in this intentionally small synthetic fixture.
    """
    if n_borrowers < 1:
        raise ValueError("n_borrowers must be at least 1")
    if n_snapshots < 5:
        raise ValueError("n_snapshots must be at least 5")

    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start_date, periods=n_snapshots, freq="30D")
    rows: list[dict[str, object]] = []
    scenario_names = np.array(["stable", "stress_only", "cure", "deteriorating"])
    scenario_probabilities = np.array([0.68, 0.12, 0.08, 0.12])

    for i in range(n_borrowers):
        borrower_id = f"SYN-BORR-{i + 1:06d}"
        account_id = f"SYN-ACCT-{i + 1:06d}"
        scenario = str(rng.choice(scenario_names, p=scenario_probabilities))
        risk = float(rng.beta(2.0, 5.0))
        balance = float(rng.integers(20_000, 2_000_000))
        start_idx = int(rng.integers(1, max(2, n_snapshots - 5)))
        cure_idx: int | None = None
        if scenario == "cure":
            cure_idx = min(start_idx + int(rng.integers(2, 4)), n_snapshots - 1)
        elif scenario == "deteriorating" and rng.random() < 0.35:
            cure_idx = min(start_idx + int(rng.integers(5, 8)), n_snapshots - 1)

        # Follow-up truncation is a property of the synthetic observation process.
        # It creates right-censored labels without pretending missing time is negative.
        coverage_idx = int(rng.integers(max(4, n_snapshots - 7), n_snapshots))
        dpd = 0
        prior_dpd = 0
        npa_active = False
        for j, date in enumerate(dates[: coverage_idx + 1]):
            if scenario in {"cure", "deteriorating"} and j >= start_idx:
                if cure_idx is not None and j >= cure_idx:
                    dpd = 0
                    npa_active = False
                else:
                    dpd = min(180, dpd + 30)
                    if dpd > 90:
                        npa_active = True
            else:
                dpd = 0
                npa_active = False

            if scenario == "stress_only" and start_idx <= j < start_idx + 3:
                stress_score = float(np.clip(0.74 + rng.normal(0, 0.06), 0, 1))
            elif scenario == "deteriorating" and j >= start_idx:
                stress_score = float(np.clip(0.42 + 0.045 * (j - start_idx) + risk * 0.25 + rng.normal(0, 0.07), 0, 1))
            elif scenario == "cure" and start_idx <= j < (cure_idx or n_snapshots):
                stress_score = float(np.clip(0.45 + risk * 0.25 + rng.normal(0, 0.08), 0, 1))
            else:
                stress_score = float(np.clip(0.18 + risk * 0.35 + rng.normal(0, 0.08), 0, 1))

            utilization = float(np.clip(0.25 + risk * 0.45 + (0.18 if dpd > 0 else 0) + rng.normal(0, 0.1), 0, 1))
            repayment_ratio = 1.0 if dpd == 0 else float(np.clip(0.7 - dpd / 250 + rng.normal(0, 0.1), 0, 1))
            overdue = float(round(balance * min(dpd / 180, 0.5), 2)) if dpd else 0.0
            npa_status = "npa" if npa_active else "standard"
            previous_npa = j > 0 and prior_npa_active
            npa_entry = bool(npa_active and not previous_npa)
            cure_event = bool(j > 0 and prior_dpd > 0 and dpd == 0)
            rows.append(
                {
                    "dataset_version": DATASET_VERSION,
                    "is_synthetic": True,
                    "bank_id": "SYN-BANK-001",
                    "borrower_id": borrower_id,
                    "account_id": account_id,
                    "snapshot_date": date,
                    "days_past_due": int(dpd),
                    "overdue_amount_inr": overdue,
                    "outstanding_balance_inr": round(balance, 2),
                    "repayment_ratio_30d": round(repayment_ratio, 4),
                    "credit_utilization": round(utilization, 4),
                    "cashflow_stress_score": round(stress_score, 4),
                    "synthetic_stress_event": bool(stress_score >= 0.70),
                    "synthetic_cure_event": cure_event,
                    "synthetic_asset_status": npa_status,
                    "npa_entry_event": npa_entry,
                    "observation_coverage_end": dates[coverage_idx],
                }
            )
            prior_npa_active = npa_active
            prior_dpd = dpd

    history = pd.DataFrame(rows, columns=HISTORY_COLUMNS)
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
    history["observation_coverage_end"] = pd.to_datetime(history["observation_coverage_end"])
    return history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--borrowers", type=int, default=400)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--snapshots", type=int, default=16)
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    from .labels import label_observations
    from .validation import validate_history, validate_labeled_observations

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    history = generate_synthetic_history(args.borrowers, args.seed, args.start_date, args.snapshots)
    labels = label_observations(history)
    validate_history(history)
    validate_labeled_observations(labels)
    history.to_csv(output_dir / "account_history.csv", index=False, date_format="%Y-%m-%d")
    labels.to_csv(output_dir / "labeled_observations.csv", index=False, date_format="%Y-%m-%d")
    metadata = {
        "dataset_version": DATASET_VERSION,
        "seed": args.seed,
        "borrowers": args.borrowers,
        "snapshots_requested": args.snapshots,
        "start_date": args.start_date,
        "generator": "synthetic_gnpa.generator.generate_synthetic_history",
        "all_records_synthetic": True,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote synthetic history and labels to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
