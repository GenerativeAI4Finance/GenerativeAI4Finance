"""Transparent cost-sensitive analysis over explicit thresholds and assumptions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CostAssumption:
    """A scenario of per-case costs; values are user-supplied, not defaults."""

    name: str
    missed_stress_case_cost: float
    false_alarm_cost: float
    cost_unit: str
    rationale: str


def _validated_inputs(
    y_true: Iterable[Any],
    y_score: Iterable[float],
    thresholds: Iterable[float],
    assumptions: Iterable[CostAssumption],
    pos_label: Any,
) -> tuple[np.ndarray, np.ndarray, list[float], list[CostAssumption], Any]:
    labels = np.asarray(list(y_true))
    scores = np.asarray(list(y_score), dtype=float)
    if labels.ndim != 1 or scores.ndim != 1:
        raise ValueError("y_true and y_score must be one-dimensional")
    if labels.size == 0:
        raise ValueError("y_true and y_score must not be empty")
    if labels.size != scores.size:
        raise ValueError("y_true and y_score must have the same length")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ValueError("y_score must contain finite probabilities in [0, 1]")

    unique_labels = list(dict.fromkeys(labels.tolist()))
    if len(unique_labels) != 2:
        raise ValueError("y_true must contain exactly two classes")
    if pos_label not in unique_labels:
        raise ValueError(f"pos_label={pos_label!r} is not present in y_true")

    threshold_values = [float(value) for value in thresholds]
    if not threshold_values:
        raise ValueError("thresholds must contain at least one value")
    if not np.isfinite(threshold_values).all() or any(not 0 <= value <= 1 for value in threshold_values):
        raise ValueError("each threshold must be finite and in [0, 1]")

    scenarios = list(assumptions)
    if not scenarios:
        raise ValueError("assumptions must contain at least one cost scenario")
    if not all(isinstance(item, CostAssumption) for item in scenarios):
        raise TypeError("assumptions must contain CostAssumption values")
    names = [item.name for item in scenarios]
    if len(set(names)) != len(names):
        raise ValueError("cost assumption names must be unique")
    for item in scenarios:
        if not item.name.strip() or not item.cost_unit.strip() or not item.rationale.strip():
            raise ValueError("each cost assumption needs a name, unit, and rationale")
        costs = [item.missed_stress_case_cost, item.false_alarm_cost]
        if not np.isfinite(costs).all() or any(value < 0 for value in costs):
            raise ValueError("costs must be finite and non-negative")
        if not any(value > 0 for value in costs):
            raise ValueError("at least one cost in each scenario must be greater than zero")

    return labels, scores, threshold_values, scenarios, pos_label


def cost_sensitive_threshold_report(
    y_true: Iterable[Any],
    y_score: Iterable[float],
    thresholds: Iterable[float],
    assumptions: Iterable[CostAssumption],
    *,
    pos_label: Any = 1,
) -> pd.DataFrame:
    """Calculate false-negative/false-positive costs for every scenario/threshold.

    A positive prediction is made when score >= threshold, matching G4F-GNPA-003.
    `missed_stress_case_cost` is charged per false negative; `false_alarm_cost`
    is charged per false positive. No threshold is selected by this function.
    """
    labels, scores, threshold_values, scenarios, pos_label = _validated_inputs(
        y_true, y_score, thresholds, assumptions, pos_label
    )
    negative_label = next(value for value in dict.fromkeys(labels.tolist()) if value != pos_label)
    rows: list[dict[str, Any]] = []

    for scenario in scenarios:
        for threshold in threshold_values:
            predicted_positive = scores >= threshold
            actual_positive = labels == pos_label
            tp = int(np.sum(predicted_positive & actual_positive))
            fp = int(np.sum(predicted_positive & ~actual_positive))
            fn = int(np.sum(~predicted_positive & actual_positive))
            tn = int(np.sum(~predicted_positive & ~actual_positive))
            missed_cost = fn * scenario.missed_stress_case_cost
            alarm_cost = fp * scenario.false_alarm_cost
            total_cost = missed_cost + alarm_cost
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            rows.append(
                {
                    "cost_assumption": scenario.name,
                    "cost_rationale": scenario.rationale,
                    "cost_unit": scenario.cost_unit,
                    "missed_stress_case_cost": float(scenario.missed_stress_case_cost),
                    "false_alarm_cost": float(scenario.false_alarm_cost),
                    "threshold": threshold,
                    "positive_label": pos_label,
                    "negative_label": negative_label,
                    "n_observations": int(labels.size),
                    "tn": tn,
                    "fp": fp,
                    "fn": fn,
                    "tp": tp,
                    "precision": float(precision),
                    "recall": float(recall),
                    "f1": float(f1),
                    "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
                    "missed_stress_total_cost": float(missed_cost),
                    "false_alarm_total_cost": float(alarm_cost),
                    "total_cost": float(total_cost),
                    "cost_per_observation": float(total_cost / labels.size),
                }
            )
    return pd.DataFrame(rows)
