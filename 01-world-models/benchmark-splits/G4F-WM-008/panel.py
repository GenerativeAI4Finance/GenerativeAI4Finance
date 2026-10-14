"""Input contract for the split generator and leakage checks.

The data is a long-format panel: one row per (entity, prediction time).
Feature columns must be known at the row's timestamp. The target is an
outcome observed over (timestamp, timestamp + horizon].
"""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class PanelSpec:
    feature_cols: list[str]
    target_col: str
    horizon: pd.DateOffset | pd.Timedelta
    entity_col: str = "entity_id"
    time_col: str = "timestamp"
    # Fields that only exist once the outcome is known (recoveries,
    # write-off amounts, cure dates...). They must never be features.
    post_outcome_cols: list[str] = field(default_factory=list)
    # feature -> column holding the time that feature value became known.
    observed_at: dict[str, str] = field(default_factory=dict)

    def validate(self, df: pd.DataFrame) -> None:
        needed = [self.entity_col, self.time_col, self.target_col, *self.feature_cols]
        needed += list(self.observed_at.values())
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"missing columns: {missing}")
        if not pd.api.types.is_datetime64_any_dtype(df[self.time_col]):
            raise ValueError(f"{self.time_col} must be a datetime column")
        if df.duplicated([self.entity_col, self.time_col]).any():
            raise ValueError("duplicate (entity, timestamp) rows")

    def describe(self) -> dict:
        return {
            "entity_col": self.entity_col,
            "time_col": self.time_col,
            "target_col": self.target_col,
            "feature_cols": list(self.feature_cols),
            "post_outcome_cols": list(self.post_outcome_cols),
            "observed_at": dict(self.observed_at),
            "horizon": str(self.horizon),
        }
