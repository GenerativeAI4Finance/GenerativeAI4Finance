"""Temporal record validation and machine-readable quality report creation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES = PACKAGE_ROOT / "config" / "validation_rules.json"

CHECK_TITLES = {
    "duplicate_keys": "Primary key uniqueness",
    "missing_timestamps": "Required timestamps",
    "impossible_transitions": "State transition validity",
    "unit_consistency": "Feature unit consistency",
    "invalid_ranges": "Configured value ranges",
    "future_data_leakage": "Feature and outcome time boundary",
    "split_assignment_integrity": "Split assignment integrity",
    "split_temporal_order": "Chronological split order",
    "split_entity_disjointness": "Entity separation across splits",
}


def _read_rules(rules: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if rules is None:
        return json.loads(DEFAULT_RULES.read_text(encoding="utf-8"))
    if isinstance(rules, dict):
        return rules
    return json.loads(Path(rules).read_text(encoding="utf-8"))


def _timestamp(value: Any) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(parsed) else pd.Timestamp(parsed)


def validate_dataset(
    payload: dict[str, Any],
    rules: dict[str, Any] | str | Path | None = None,
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Return a check-by-check report; invalid input is represented, not raised.

    Records use `record_id`, `entity_id`, `timestamp`, `state`, feature mappings
    (`value`, `unit`, `available_at`), and optional `outcome.observed_at`. Split
    rows repeat the record ID, entity, timestamp, and one of train/validation/test.
    """
    cfg = _read_rules(rules)
    records = payload.get("records", [])
    split_rows = payload.get("splits", [])
    issues: dict[str, list[dict[str, Any]]] = {name: [] for name in CHECK_TITLES}

    def issue(check: str, code: str, message: str, **context: Any) -> None:
        issues[check].append({"code": code, "message": message, **context})

    # Core records: IDs, timestamps, duplicate entity/time keys, states, units,
    # numeric bounds, and point-in-time leakage.
    if not records:
        issue("split_assignment_integrity", "dataset_empty", "Dataset must contain at least one record.")
    df = pd.DataFrame(records)
    if not df.empty:
        for field in ("record_id", "entity_id", "timestamp", "state"):
            if field not in df:
                df[field] = None
        for row in records:
            record_id = row.get("record_id")
            if not row.get("record_id") or not row.get("entity_id"):
                issue("split_assignment_integrity", "missing_record_or_entity_id", "Record must have record_id and entity_id.", record_id=record_id)
            record_time = _timestamp(row.get("timestamp"))
            if record_time is None:
                issue("missing_timestamps", "record_timestamp_missing_or_invalid", "Record timestamp is missing or invalid.", record_id=record_id, timestamp=row.get("timestamp"))
            features = row.get("features") or {}
            if not isinstance(features, dict):
                issue("unit_consistency", "features_not_object", "Features must be an object keyed by feature name.", record_id=record_id)
                features = {}
            for feature_name, feature in features.items():
                if not isinstance(feature, dict):
                    issue("unit_consistency", "feature_not_object", "Each feature must contain a value and metadata object.", record_id=record_id, feature=feature_name)
                    continue
                expected_unit = cfg.get("expected_units", {}).get(feature_name)
                if expected_unit is not None and feature.get("unit") != expected_unit:
                    issue("unit_consistency", "unexpected_unit", "Feature unit does not match configured unit.", record_id=record_id, feature=feature_name, expected=expected_unit, actual=feature.get("unit"))
                value = feature.get("value")
                bounds = cfg.get("value_ranges", {}).get(feature_name)
                if value is not None and bounds is not None:
                    try:
                        numeric_value = float(value)
                        if numeric_value < bounds["min"] or numeric_value > bounds["max"]:
                            issue("invalid_ranges", "value_out_of_range", "Feature value is outside configured limits.", record_id=record_id, feature=feature_name, value=value, minimum=bounds["min"], maximum=bounds["max"])
                    except (TypeError, ValueError):
                        issue("invalid_ranges", "non_numeric_value", "Configured numeric feature has a non-numeric value.", record_id=record_id, feature=feature_name, value=value)
                available_at = _timestamp(feature.get("available_at"))
                if available_at is None:
                    issue("future_data_leakage", "feature_availability_missing_or_invalid", "Feature availability timestamp is missing or invalid.", record_id=record_id, feature=feature_name)
                elif record_time is not None and available_at > record_time:
                    issue("future_data_leakage", "feature_available_after_record_time", "Feature was not available at the record timestamp.", record_id=record_id, feature=feature_name, available_at=available_at.isoformat(), record_timestamp=record_time.isoformat())
            outcome = row.get("outcome")
            if outcome is not None:
                outcome_time = _timestamp(outcome.get("observed_at")) if isinstance(outcome, dict) else None
                if outcome_time is None:
                    issue("future_data_leakage", "outcome_timestamp_missing_or_invalid", "Outcome must include a valid observation timestamp.", record_id=record_id)
                elif record_time is not None and outcome_time <= record_time:
                    issue("future_data_leakage", "outcome_not_future", "Outcome timestamp must be after the observation timestamp.", record_id=record_id, outcome_timestamp=outcome_time.isoformat(), record_timestamp=record_time.isoformat())

        primary_key = cfg.get("primary_key", ["entity_id", "timestamp"])
        if all(column in df for column in primary_key):
            duplicate_mask = df.duplicated(primary_key, keep=False)
            for _, row in df[duplicate_mask].iterrows():
                issue("duplicate_keys", "duplicate_primary_key", "Primary key values occur more than once.", record_id=row.get("record_id"), key={column: row.get(column) for column in primary_key})
        duplicate_record_ids = df[df["record_id"].notna() & df["record_id"].duplicated(keep=False)]
        for _, row in duplicate_record_ids.iterrows():
            issue("split_assignment_integrity", "duplicate_record_id", "record_id must be unique.", record_id=row.get("record_id"))

        allowed_transitions = cfg.get("allowed_state_transitions", {})
        state_frame = df.copy()
        state_frame["_timestamp"] = pd.to_datetime(state_frame["timestamp"], utc=True, errors="coerce")
        state_frame = state_frame.dropna(subset=["_timestamp"]).sort_values(["entity_id", "_timestamp", "record_id"], kind="stable")
        for entity_id, group in state_frame.groupby("entity_id", dropna=False, sort=False):
            previous = None
            for _, row in group.iterrows():
                state = row.get("state")
                if not isinstance(state, str) or state not in allowed_transitions:
                    issue("impossible_transitions", "unknown_or_missing_state", "State is missing or absent from the configured transition graph.", entity_id=entity_id, state=state, record_id=row.get("record_id"))
                if previous is not None and state not in allowed_transitions.get(previous["state"], []):
                    issue("impossible_transitions", "transition_not_allowed", "State transition is not in configured transition graph.", entity_id=entity_id, from_state=previous["state"], to_state=state, from_record_id=previous["record_id"], to_record_id=row.get("record_id"))
                previous = {"state": state, "record_id": row.get("record_id")}

    # Split table: one assignment per record, matching entity/time, chronological
    # cut points, and optionally disjoint entities.
    split_df = pd.DataFrame(split_rows)
    record_ids = {row.get("record_id") for row in records if row.get("record_id")}
    record_by_id = {row.get("record_id"): row for row in records if row.get("record_id")}
    if not split_df.empty:
        required_columns = {"record_id", "entity_id", "timestamp", "split"}
        missing_columns = required_columns - set(split_df.columns)
        if missing_columns:
            issue("split_assignment_integrity", "split_fields_missing", "Split assignments are missing required fields.", fields=sorted(missing_columns))
        else:
            for _, split_row in split_df.iterrows():
                record_id = split_row["record_id"]
                record = record_by_id.get(record_id)
                if record is None:
                    issue("split_assignment_integrity", "unknown_split_record", "Split assignment references an unknown record.", record_id=record_id)
                    continue
                if split_row["entity_id"] != record.get("entity_id"):
                    issue("split_assignment_integrity", "split_entity_mismatch", "Split entity_id does not match its record.", record_id=record_id)
                split_time, record_time = _timestamp(split_row["timestamp"]), _timestamp(record.get("timestamp"))
                if split_time is None or record_time is None or split_time != record_time:
                    issue("split_assignment_integrity", "split_timestamp_mismatch", "Split timestamp must match the record timestamp.", record_id=record_id)
                if split_row["split"] not in cfg.get("required_splits", []):
                    issue("split_assignment_integrity", "unknown_split_name", "Split label is not configured.", record_id=record_id, split=split_row["split"])
            for record_id in sorted(record_ids - set(split_df["record_id"])):
                issue("split_assignment_integrity", "record_unassigned", "Record has no split assignment.", record_id=record_id)
            for record_id in split_df.loc[split_df["record_id"].duplicated(keep=False), "record_id"].dropna().unique():
                issue("split_assignment_integrity", "record_assigned_multiple_times", "Record has more than one split assignment.", record_id=record_id)
            absent_splits = set(cfg.get("required_splits", [])) - set(split_df["split"].dropna())
            if absent_splits:
                issue("split_assignment_integrity", "required_split_empty", "A required split has no assignments.", splits=sorted(absent_splits))

            order = cfg.get("split_order", cfg.get("required_splits", []))
            valid_split_df = split_df[split_df["split"].isin(order)].copy()
            valid_split_df["_timestamp"] = pd.to_datetime(valid_split_df["timestamp"], utc=True, errors="coerce")
            for earlier, later in zip(order, order[1:]):
                earlier_times = valid_split_df.loc[(valid_split_df["split"] == earlier) & valid_split_df["_timestamp"].notna(), "_timestamp"]
                later_times = valid_split_df.loc[(valid_split_df["split"] == later) & valid_split_df["_timestamp"].notna(), "_timestamp"]
                if earlier_times.empty or later_times.empty:
                    issue("split_temporal_order", "split_has_no_valid_timestamps", "Adjacent splits must have valid timestamps to verify order.", earlier_split=earlier, later_split=later)
                elif earlier_times.max() >= later_times.min():
                    issue("split_temporal_order", "time_order_violation", "Earlier split contains a timestamp at or after the next split begins.", earlier_split=earlier, earlier_max=earlier_times.max().isoformat(), later_split=later, later_min=later_times.min().isoformat())
            if cfg.get("entity_disjoint_splits", True):
                for entity_id, group in split_df.groupby("entity_id", dropna=False, sort=False):
                    split_names = sorted(set(group["split"].dropna()))
                    if len(split_names) > 1:
                        issue("split_entity_disjointness", "entity_crosses_splits", "Entity appears in more than one data split.", entity_id=entity_id, splits=split_names)
    elif records:
        issue("split_assignment_integrity", "split_table_missing", "Split assignments are required for every dataset record.")

    checks = []
    for check_id, title in CHECK_TITLES.items():
        check_issues = issues[check_id]
        checks.append({"check_id": check_id, "title": title, "status": "fail" if check_issues else "pass", "issue_count": len(check_issues), "issues": check_issues})
    total_issues = sum(len(items) for items in issues.values())
    return {
        "report_version": "1.0.0",
        "dataset_id": payload.get("dataset_id", "unknown"),
        "synthetic": payload.get("synthetic", False),
        "generated_at_utc": generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rules_version": cfg.get("rules_version", "unversioned"),
        "record_count": len(records),
        "split_assignment_count": len(split_rows),
        "summary": {"status": "fail" if total_issues else "pass", "check_count": len(checks), "failed_check_count": sum(check["status"] == "fail" for check in checks), "issue_count": total_issues},
        "checks": checks,
    }
