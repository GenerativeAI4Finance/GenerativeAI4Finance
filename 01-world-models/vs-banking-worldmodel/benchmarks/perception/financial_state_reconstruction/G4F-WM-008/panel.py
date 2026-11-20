"""Input contract for the split generator and leakage checks.

The data is a long-format panel: one row per (entity, prediction time).
Feature columns must be known at the row's timestamp. The target is an
outcome observed over (timestamp, timestamp + horizon].
"""

from dataclasses import dataclass, field

import pandas as pd


def horizon_ends(times: pd.Series, horizon: pd.DateOffset | pd.Timedelta) -> pd.Series:
    """Apply an outcome horizon without pandas' implicit scalar fallback."""
    if isinstance(horizon, pd.DateOffset):
        try:
            # Pinned pandas 3.0.6 uses this private capability check before
            # falling back to scalar arithmetic with a PerformanceWarning.
            # Recheck the dispatch when upgrading pandas. An empty probe keeps
            # supported offsets on the native vectorized path, including DST.
            horizon._apply_array(
                pd.DatetimeIndex([], dtype="datetime64[ns]").to_numpy()
            )
        except NotImplementedError:
            # Keep Timestamp arithmetic: converting to Python datetime would
            # lose nanoseconds. Let pandas infer any finer output resolution.
            return pd.Series(
                [timestamp + horizon for timestamp in times],
                index=times.index,
                name=times.name,
            )
    return times + horizon


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
        if df.empty:
            raise ValueError("the panel has no rows")
        times = df[self.time_col]
        if not pd.api.types.is_datetime64_any_dtype(times):
            raise ValueError(f"{self.time_col} must be a datetime column")
        if times.isna().any():
            raise ValueError(
                f"{self.time_col} has {int(times.isna().sum())} missing values (NaT)"
            )
        valid_horizon = isinstance(self.horizon, (pd.DateOffset, pd.Timedelta))
        if valid_horizon:
            try:
                ends = horizon_ends(times, self.horizon)
                valid_horizon = bool(ends.notna().all() and (ends > times).all())
            except (ValueError, TypeError, OverflowError):
                valid_horizon = False
        if not valid_horizon:
            raise ValueError(
                "horizon must be a DateOffset or Timedelta that is positive "
                "and finite on every row"
            )
        n_missing = int(df[self.entity_col].isna().sum())
        if n_missing:
            raise ValueError(f"{self.entity_col} has {n_missing} missing values")
        if not pd.api.types.is_numeric_dtype(df[self.target_col]):
            raise ValueError(
                f"target {self.target_col} must be numeric (0/1 for a binary target)"
            )
        for col in self.observed_at.values():
            seen = df[col]
            if not pd.api.types.is_datetime64_any_dtype(seen):
                raise ValueError(f"observed_at column {col} must be a datetime column")
            if (seen.dt.tz is None) != (times.dt.tz is None):
                raise ValueError(
                    f"observed_at column {col} and {self.time_col} must both be "
                    "timezone-aware or both naive"
                )
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
