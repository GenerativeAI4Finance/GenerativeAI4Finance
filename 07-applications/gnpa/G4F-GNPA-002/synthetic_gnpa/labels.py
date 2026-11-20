"""Create point-in-time labels from simulated histories."""

from __future__ import annotations

import pandas as pd

from .generator import HISTORY_COLUMNS

HORIZON_DAYS = 90
FEATURE_COLUMNS = [
    "dataset_version",
    "is_synthetic",
    "bank_id",
    "borrower_id",
    "account_id",
    "observation_date",
    "days_past_due",
    "overdue_amount_inr",
    "outstanding_balance_inr",
    "repayment_ratio_30d",
    "credit_utilization",
    "cashflow_stress_score",
    "synthetic_stress_event",
    "synthetic_cure_event",
    "synthetic_asset_status_at_t",
]
TARGET_COLUMNS = [
    "delinquency_30plus_within_90d",
    "stress_event_within_90d",
    "new_npa_within_90d",
    "cure_within_90d",
]
AUDIT_COLUMNS = [
    "eligibility_status_at_t",
    "horizon_end_date",
    "outcome_observed_through",
    "censor_reason",
    "delinquency_event_date",
    "stress_event_date",
    "first_npa_effective_date",
    "cure_event_date",
]


def _first_event_date(future: pd.DataFrame, mask: pd.Series) -> pd.Timestamp | pd.NaT:
    selected = future.loc[mask, "snapshot_date"]
    return selected.iloc[0] if not selected.empty else pd.NaT


def _event_or_censor(event_date: pd.Timestamp | pd.NaT, horizon_end: pd.Timestamp, coverage_end: pd.Timestamp) -> object:
    if pd.notna(event_date) and event_date <= horizon_end and event_date <= coverage_end:
        return 1
    if coverage_end >= horizon_end:
        return 0
    return pd.NA


def label_observations(history: pd.DataFrame, horizon_days: int = HORIZON_DAYS) -> pd.DataFrame:
    """Return model-ready point-in-time rows plus separate label/audit columns.

    Labels are based on future synthetic outcomes by design. Predictor columns are
    limited to values present at the observation snapshot. `*_event_date`, horizon,
    coverage and target fields are audit/outcome fields and must not be predictors.
    """
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    missing = set(HISTORY_COLUMNS) - set(history.columns)
    if missing:
        raise ValueError(f"history missing required columns: {sorted(missing)}")

    source = history.copy()
    source["snapshot_date"] = pd.to_datetime(source["snapshot_date"])
    source["observation_coverage_end"] = pd.to_datetime(source["observation_coverage_end"])
    records: list[dict[str, object]] = []

    for borrower_id, group in source.groupby("borrower_id", sort=True):
        group = group.sort_values("snapshot_date").reset_index(drop=True)
        coverage_end = group["observation_coverage_end"].max()
        for _, current in group.iterrows():
            t = current["snapshot_date"]
            horizon_end = t + pd.Timedelta(days=horizon_days)
            future = group.loc[(group["snapshot_date"] > t) & (group["snapshot_date"] <= horizon_end)]
            eligible = current["synthetic_asset_status"] == "standard"
            delim_date = _first_event_date(future, future["days_past_due"] > 30)
            stress_date = _first_event_date(future, future["synthetic_stress_event"].astype(bool))
            npa_date = _first_event_date(future, future["npa_entry_event"].astype(bool))
            cure_date = _first_event_date(future, future["synthetic_cure_event"].astype(bool))
            row: dict[str, object] = {
                "dataset_version": current["dataset_version"],
                "is_synthetic": bool(current["is_synthetic"]),
                "bank_id": current["bank_id"],
                "borrower_id": borrower_id,
                "account_id": current["account_id"],
                "observation_date": t,
                "days_past_due": int(current["days_past_due"]),
                "overdue_amount_inr": float(current["overdue_amount_inr"]),
                "outstanding_balance_inr": float(current["outstanding_balance_inr"]),
                "repayment_ratio_30d": float(current["repayment_ratio_30d"]),
                "credit_utilization": float(current["credit_utilization"]),
                "cashflow_stress_score": float(current["cashflow_stress_score"]),
                "synthetic_stress_event": bool(current["synthetic_stress_event"]),
                "synthetic_cure_event": bool(current["synthetic_cure_event"]),
                "synthetic_asset_status_at_t": current["synthetic_asset_status"],
                "eligibility_status_at_t": "eligible" if eligible else "ineligible_already_npa",
                "horizon_end_date": horizon_end,
                "outcome_observed_through": coverage_end,
                "censor_reason": "follow_up_ends_before_horizon" if coverage_end < horizon_end else "",
                "delinquency_event_date": delim_date,
                "stress_event_date": stress_date,
                "first_npa_effective_date": npa_date,
                "cure_event_date": cure_date,
                "delinquency_30plus_within_90d": pd.NA if not eligible else _event_or_censor(delim_date, horizon_end, coverage_end),
                "stress_event_within_90d": pd.NA if not eligible else _event_or_censor(stress_date, horizon_end, coverage_end),
                "new_npa_within_90d": pd.NA if not eligible else _event_or_censor(npa_date, horizon_end, coverage_end),
                "cure_within_90d": pd.NA if not eligible else _event_or_censor(cure_date, horizon_end, coverage_end),
            }
            records.append(row)

    result = pd.DataFrame.from_records(records, columns=FEATURE_COLUMNS + AUDIT_COLUMNS + TARGET_COLUMNS)
    for col in TARGET_COLUMNS:
        result[col] = result[col].astype("Int64")
    return result
