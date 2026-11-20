"""Train and evaluate a baseline against a majority-class reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TASK_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = TASK_DIR / "config" / "evaluation.json"
DEFAULT_DATA = TASK_DIR / "data" / "sample" / "synthetic_panel.csv"
DEFAULT_OUTPUT = TASK_DIR / "reports"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    required = {"target", "horizon_months", "feature_columns", "validation_start", "test_start", "seed"}
    missing = required - config.keys()
    if missing:
        raise ValueError(f"evaluation config is missing: {sorted(missing)}")
    if config["target"] in config["feature_columns"]:
        raise ValueError("target cannot be a model feature")
    if set(config["feature_columns"]) & set(config.get("excluded_post_outcome_columns", [])):
        raise ValueError("post-outcome fields cannot be model features")
    if config["horizon_months"] < 1:
        raise ValueError("horizon_months must be positive")
    return config


def temporal_split(frame: pd.DataFrame, config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Assign out-of-time splits and purge rows whose label window crosses a cutoff."""
    required = {
        config["timestamp_column"], config["target"], config.get("entity_column", "entity_id"),
        *config["feature_columns"], *config.get("observed_at", {}).values(),
    }
    if not required.issubset(frame.columns):
        raise ValueError(f"panel is missing required columns: {sorted(required - set(frame.columns))}")
    if frame[config["timestamp_column"]].isna().any():
        raise ValueError("timestamps may not be missing")
    result = frame.copy()
    times = pd.to_datetime(result[config["timestamp_column"]])
    entity_column = config.get("entity_column", "entity_id")
    if result[entity_column].isna().any():
        raise ValueError("entity identifiers may not be missing")
    if result.duplicated([entity_column, config["timestamp_column"]]).any():
        raise ValueError("duplicate entity/timestamp rows are not allowed")
    target_values = result[config["target"]]
    if target_values.isna().any() or not set(target_values.unique()).issubset({0, 1}):
        raise ValueError("binary target must be complete and contain only 0/1 values")
    for feature in config["feature_columns"]:
        if result[feature].isna().any() or not pd.api.types.is_numeric_dtype(result[feature]):
            raise ValueError(f"feature {feature} must be complete and numeric")
    for feature, observed_at_column in config.get("observed_at", {}).items():
        observed_at = pd.to_datetime(result[observed_at_column])
        if observed_at.isna().any() or (observed_at > times).any():
            raise ValueError(f"feature {feature} is missing or observed after prediction time")
    valid_start = pd.Timestamp(config["validation_start"])
    test_start = pd.Timestamp(config["test_start"])
    if (times.dt.tz is None) != (valid_start.tz is None) or (times.dt.tz is None) != (test_start.tz is None):
        raise ValueError("timestamps and split cutoffs must have matching timezone awareness")
    if valid_start >= test_start:
        raise ValueError("validation_start must precede test_start")
    horizon_end = times + pd.DateOffset(months=config["horizon_months"])
    split = pd.Series("drop", index=result.index, dtype="object")
    split[horizon_end <= valid_start] = "train"
    split[(times >= valid_start) & (horizon_end <= test_start)] = "validation"
    split[times >= test_start] = "test"
    result["split"] = split
    summary = {}
    for name in ("train", "validation", "test", "drop"):
        part = result.loc[result["split"] == name]
        summary[name] = {
            "rows": int(len(part)),
            "entities": int(part[entity_column].nunique()) if entity_column in part else 0,
            "min_timestamp": part[config["timestamp_column"]].min().isoformat() if len(part) else None,
            "max_timestamp": part[config["timestamp_column"]].max().isoformat() if len(part) else None,
        }
    if any(summary[name]["rows"] == 0 for name in ("train", "validation", "test")):
        raise ValueError(f"time split produced an empty split: {summary}")
    return result, summary


def utilisation_band(values: pd.Series) -> pd.Series:
    return pd.cut(values, bins=[-np.inf, 0.5, 0.8, np.inf], labels=["low", "medium", "high"], right=True).astype("object")


def _metrics(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, Any]:
    y = y_true.astype(int).to_numpy()
    predicted = (probabilities >= threshold).astype(int)
    both_classes = len(np.unique(y)) == 2
    return {
        "n": int(len(y)),
        "positive_rate": round(float(y.mean()), 6) if len(y) else None,
        "accuracy": round(float(accuracy_score(y, predicted)), 6) if len(y) else None,
        "balanced_accuracy": round(float(balanced_accuracy_score(y, predicted)), 6) if len(y) and both_classes else None,
        "precision": round(float(precision_score(y, predicted, zero_division=0)), 6) if len(y) else None,
        "recall": round(float(recall_score(y, predicted, zero_division=0)), 6) if len(y) else None,
        "f1": round(float(f1_score(y, predicted, zero_division=0)), 6) if len(y) else None,
        "roc_auc": round(float(roc_auc_score(y, probabilities)), 6) if both_classes else None,
        "average_precision": round(float(average_precision_score(y, probabilities)), 6) if len(y) and y.sum() > 0 else None,
        "brier_score": round(float(brier_score_loss(y, probabilities)), 6) if len(y) else None,
    }


def _model_predictions(training: pd.DataFrame, frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, np.ndarray]:
    features = config["feature_columns"]
    target = config["target"]
    y_train = training[target].astype(int)
    if y_train.nunique() != 2:
        raise ValueError("training split must contain both target classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=config["model"]["C"],
            max_iter=config["model"]["max_iter"],
            class_weight=config["model"]["class_weight"],
            random_state=config["seed"],
        ),
    )
    model.fit(training[features], y_train)
    naive = DummyClassifier(strategy="most_frequent")
    naive.fit(training[features], y_train)
    return {
        "logistic_regression": model.predict_proba(frame[features])[:, 1],
        "majority_class": naive.predict_proba(frame[features])[:, list(naive.classes_).index(1)],
    }


def evaluate(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    split_frame, split_summary = temporal_split(frame, config)
    target = config["target"]
    train = split_frame.loc[split_frame["split"] == "train"]
    model_names = ("logistic_regression", "majority_class")
    overall: dict[str, Any] = {}
    predictions: dict[str, dict[Any, float]] = {model: {} for model in model_names}
    for split_name in ("validation", "test"):
        part = split_frame.loc[split_frame["split"] == split_name].copy()
        probabilities = _model_predictions(train, part, config)
        overall[split_name] = {}
        for model_name, scores in probabilities.items():
            overall[split_name][model_name] = _metrics(part[target], scores, config["threshold"])
            predictions[model_name].update(dict(zip(part.index, scores, strict=True)))

    test = split_frame.loc[split_frame["split"] == "test"].copy()
    test["quarter"] = pd.to_datetime(test[config["timestamp_column"]]).dt.to_period("Q").astype(str)
    subgroup_config = config["subgroup_definition"]
    test[subgroup_config["name"]] = utilisation_band(test[subgroup_config["column"]])
    by_period: dict[str, Any] = {}
    for period, part in test.groupby("quarter", observed=True, sort=True):
        by_period[str(period)] = {
            model: _metrics(part[target], np.array([predictions[model][idx] for idx in part.index]), config["threshold"])
            for model in model_names
        }
    by_subgroup: dict[str, Any] = {}
    for subgroup, part in test.groupby(subgroup_config["name"], observed=True, sort=True):
        by_subgroup[str(subgroup)] = {
            model: _metrics(part[target], np.array([predictions[model][idx] for idx in part.index]), config["threshold"])
            for model in model_names
        }
    return {
        "evaluation_version": config["evaluation_version"],
        "dataset_version": config["dataset_version"],
        "target": config["target"],
        "target_definition": config["target_definition"],
        "horizon_months": config["horizon_months"],
        "split_policy": config["split_policy"],
        "split_summary": split_summary,
        "overall": overall,
        "test_by_quarter": by_period,
        "test_by_utilisation_band": by_subgroup,
        "metric_notes": {
            "threshold": config["threshold"],
            "undefined_metrics": "ROC AUC and balanced accuracy are null for one-class groups; average precision is null when a group has no positive rows.",
            "naive_baseline": "Training-split most frequent class; same predicted probability is used for every validation/test row.",
        },
    }


def run(config_path: Path = DEFAULT_CONFIG, data_path: Path = DEFAULT_DATA, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    config = load_config(config_path)
    frame = pd.read_csv(data_path, parse_dates=[config["timestamp_column"], "dpd_observed_at"])
    metrics = evaluate(frame, config)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "baseline_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    data_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    manifest = {
        "dataset_sha256": data_hash,
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "evaluation_sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
        "runtime_versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scikit_learn": sklearn.__version__},
        "random_seed": config["seed"],
        "feature_columns": config["feature_columns"],
        "target": config["target"],
        "horizon_months": config["horizon_months"],
        "model": config["model"],
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"metrics": metrics, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.config, args.data, args.output_dir)
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
