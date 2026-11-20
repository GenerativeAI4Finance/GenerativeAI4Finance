"""Schema and point-in-time validation for generated synthetic data."""

from __future__ import annotations

import pandas as pd

from .generator import HISTORY_COLUMNS
from .labels import AUDIT_COLUMNS, FEATURE_COLUMNS, TARGET_COLUMNS


def validate_history(history: pd.DataFrame) -> None:
    missing = set(HISTORY_COLUMNS) - set(history.columns)
    if missing:
        raise ValueError(f"history missing required columns: {sorted(missing)}")
    if not history["is_synthetic"].eq(True).all():
        raise ValueError("every history row must be explicitly marked synthetic")
    if history.duplicated(["bank_id", "borrower_id", "snapshot_date"]).any():
        raise ValueError("duplicate borrower snapshot keys")
    if not history["synthetic_asset_status"].isin(["standard", "npa"]).all():
        raise ValueError("unexpected synthetic asset status")
    if not history["days_past_due"].between(0, 180).all():
        raise ValueError("days_past_due outside the generated range")
    for col in ["cashflow_stress_score", "credit_utilization", "repayment_ratio_30d"]:
        if not history[col].between(0, 1).all():
            raise ValueError(f"{col} must be in [0, 1]")
    if (history["synthetic_asset_status"].eq("npa") != history["days_past_due"].gt(90)).any():
        raise ValueError("synthetic NPA proxy must match DPD > 90 simulation rule")
    ordered = history.sort_values(["borrower_id", "snapshot_date"])
    if not ordered.groupby("borrower_id")["snapshot_date"].apply(lambda s: s.is_monotonic_increasing).all():
        raise ValueError("snapshots must increase over time within each borrower")


def validate_labeled_observations(labels: pd.DataFrame) -> None:
    required = set(FEATURE_COLUMNS + AUDIT_COLUMNS + TARGET_COLUMNS)
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"labeled observations missing required columns: {sorted(missing)}")
    if not labels["is_synthetic"].eq(True).all():
        raise ValueError("every labeled row must be explicitly marked synthetic")
    if labels.duplicated(["bank_id", "borrower_id", "observation_date"]).any():
        raise ValueError("duplicate labeled observation keys")
    if labels["observation_date"].gt(labels["outcome_observed_through"]).any():
        raise ValueError("observation date cannot be after outcome coverage end")
    forbidden_predictors = set(TARGET_COLUMNS + AUDIT_COLUMNS) - {"eligibility_status_at_t"}
    if set(FEATURE_COLUMNS) & forbidden_predictors:
        raise ValueError("target/audit fields must not appear in FEATURE_COLUMNS")
    for col in TARGET_COLUMNS:
        values = set(labels[col].dropna().astype(int).unique())
        if not values.issubset({0, 1}):
            raise ValueError(f"{col} must contain only 0, 1, or null")
        ineligible = labels["eligibility_status_at_t"].ne("eligible")
        if labels.loc[ineligible, col].notna().any():
            raise ValueError(f"ineligible records must have null {col}")
    incomplete_no_event = labels["outcome_observed_through"].lt(labels["horizon_end_date"])
    for col in TARGET_COLUMNS:
        event_col = {
            "delinquency_30plus_within_90d": "delinquency_event_date",
            "stress_event_within_90d": "stress_event_date",
            "new_npa_within_90d": "first_npa_effective_date",
            "cure_within_90d": "cure_event_date",
        }[col]
        no_observed_event = labels[event_col].isna()
        if labels.loc[incomplete_no_event & no_observed_event, col].notna().any():
            raise ValueError(f"incomplete event-free follow-up must be censored for {col}")
