"""Binary credit-risk benchmark metrics with an explicit positive class."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


def _validated_inputs(
    y_true: Iterable[Any],
    y_score: Iterable[float],
    pos_label: Any,
) -> tuple[np.ndarray, np.ndarray, Any, Any]:
    labels = np.asarray(list(y_true))
    scores = np.asarray(list(y_score), dtype=float)
    if labels.ndim != 1 or scores.ndim != 1:
        raise ValueError("y_true and y_score must be one-dimensional")
    if labels.size == 0:
        raise ValueError("y_true and y_score must not be empty")
    if labels.size != scores.size:
        raise ValueError("y_true and y_score must have the same length")
    if not np.isfinite(scores).all():
        raise ValueError("y_score must contain only finite values")
    if ((scores < 0) | (scores > 1)).any():
        raise ValueError("y_score values must be probabilities in [0, 1]")

    unique_labels = list(dict.fromkeys(labels.tolist()))
    if len(unique_labels) != 2:
        raise ValueError("y_true must contain exactly two classes")
    if pos_label not in unique_labels:
        raise ValueError(f"pos_label={pos_label!r} is not present in y_true")
    neg_label = next(label for label in unique_labels if label != pos_label)
    return labels, scores, pos_label, neg_label


def evaluate_binary_classifier(
    y_true: Iterable[Any],
    y_score: Iterable[float],
    *,
    threshold: float = 0.5,
    pos_label: Any = 1,
) -> dict[str, Any]:
    """Evaluate binary scores at one threshold and report ranking quality.

    Scores are probabilities or probability-like values in [0, 1]. A row is
    predicted positive when `score >= threshold`. PR-AUC is reported as average
    precision (the non-interpolated scikit-learn definition).
    """
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and in [0, 1]")
    labels, scores, pos_label, neg_label = _validated_inputs(y_true, y_score, pos_label)
    predicted = np.where(scores >= threshold, pos_label, neg_label)
    matrix = confusion_matrix(labels, predicted, labels=[neg_label, pos_label])
    tn, fp, fn, tp = (int(v) for v in matrix.ravel())
    precision = float(precision_score(labels, predicted, pos_label=pos_label, zero_division=0))
    recall = float(recall_score(labels, predicted, pos_label=pos_label, zero_division=0))
    f1 = float(f1_score(labels, predicted, pos_label=pos_label, zero_division=0))

    return {
        "n_samples": int(labels.size),
        "positive_label": pos_label,
        "negative_label": neg_label,
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(labels, predicted)),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "pr_auc_average_precision": float(average_precision_score(labels, scores, pos_label=pos_label)),
        "confusion_matrix": {
            "label_order": [neg_label, pos_label],
            "matrix": matrix.tolist(),
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        },
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
    }


def analyze_thresholds(
    y_true: Iterable[Any],
    y_score: Iterable[float],
    thresholds: Iterable[float],
    *,
    pos_label: Any = 1,
) -> list[dict[str, Any]]:
    """Return recall and false-positive details for each supplied threshold."""
    labels, scores, pos_label, _ = _validated_inputs(y_true, y_score, pos_label)
    values = list(thresholds)
    if not values:
        raise ValueError("thresholds must contain at least one value")
    results = []
    for threshold in values:
        result = evaluate_binary_classifier(
            labels, scores, threshold=float(threshold), pos_label=pos_label
        )
        cm = result["confusion_matrix"]
        result["false_positives"] = cm["fp"]
        result["false_positive_rate"] = cm["fp"] / (cm["fp"] + cm["tn"])
        results.append(result)
    return results
