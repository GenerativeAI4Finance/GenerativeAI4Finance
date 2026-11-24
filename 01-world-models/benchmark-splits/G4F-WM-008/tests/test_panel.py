import pandas as pd
import pytest

from leakage import check_target_leakage, check_time_order
from panel import PanelSpec, horizon_ends
from splits import make_splits

pytestmark = pytest.mark.filterwarnings("error")


@pytest.mark.parametrize("timezone", [None, "UTC", "America/New_York"])
@pytest.mark.parametrize(
    "horizon",
    [
        pd.Timedelta(hours=24, nanoseconds=1),
        pd.DateOffset(hours=24),
        pd.DateOffset(days=1),
        pd.DateOffset(months=1),
        pd.DateOffset(nanoseconds=1),
        pd.DateOffset(months=1, normalize=True),
        pd.offsets.Hour(24),
        pd.offsets.BusinessDay(),
    ],
)
def test_native_horizon_arithmetic_keeps_pandas_semantics(timezone, horizon):
    # Both DST transitions, month end and sub-microsecond precision matter.
    times = pd.Series(
        pd.DatetimeIndex(
            [
                "2024-03-09 12:00:00.123456789",
                "2024-11-02 12:00:00.123456789",
                "2024-01-31 12:00:00.123456789",
            ],
            tz=timezone,
        ),
        index=pd.Index([8, 2, 8], name="row"),
        name="prediction",
    )
    original = times.copy()
    pd.testing.assert_series_equal(horizon_ends(times, horizon), times + horizon)
    pd.testing.assert_series_equal(times, original)


@pytest.mark.parametrize("timezone", [None, "UTC", "America/New_York"])
@pytest.mark.parametrize(
    "horizon",
    [
        pd.DateOffset(year=2030, days=1),
        pd.DateOffset(months=1, day=15),
        pd.DateOffset(months=1, day=15, normalize=True),
        pd.DateOffset(weeks=1, weekday=0),
        pd.offsets.BusinessHour(),
        pd.offsets.CustomBusinessDay(),
        pd.offsets.Easter(),
    ],
)
def test_scalar_horizons_preserve_timestamps_without_warnings(timezone, horizon):
    times = pd.Series(
        pd.DatetimeIndex(
            ["2024-03-09 12:00:00.123456789", "2024-11-02 12:00:00.123456789"],
            tz=timezone,
        ),
        index=pd.Index([11, 3], name="row"),
        name="prediction",
    )
    expected = pd.Series(
        [timestamp + horizon for timestamp in times], index=times.index, name=times.name
    )
    pd.testing.assert_series_equal(horizon_ends(times, horizon), expected)


@pytest.mark.parametrize("timezone", [None, "America/New_York"])
def test_scalar_horizon_promotes_resolution_without_losing_nanoseconds(timezone):
    times = pd.Series(
        pd.DatetimeIndex(["2024-03-09 12:00:00"], tz=timezone).as_unit("us"),
        index=[9],
        name="prediction",
    )
    ends = horizon_ends(times, pd.DateOffset(year=2030, nanoseconds=1))
    expected = pd.Series(
        [pd.Timestamp("2030-03-09 12:00:00.000000001", tz=timezone)],
        index=times.index,
        name=times.name,
    )
    pd.testing.assert_series_equal(ends, expected)


def test_replacement_horizon_split_and_time_check_share_window_ends():
    df = pd.DataFrame(
        {
            "entity_id": ["a"] * 4,
            "timestamp": pd.to_datetime(
                ["2022-01-01", "2022-12-01", "2030-03-01", "2030-06-01"]
            ),
            "feature": [1, 2, 3, 4],
            "target": [0, 1, 0, 1],
        },
        index=[9, 4, 7, 1],
    )
    spec = PanelSpec(["feature"], "target", pd.DateOffset(year=2030, days=1))
    result = make_splits(
        df,
        spec,
        "time",
        valid_start="2030-03-01",
        test_start="2030-06-01",
        embargo=pd.Timedelta(nanoseconds=1),
    )
    assert result.labels.tolist() == ["train", "drop", "valid", "test"]
    assert result.labels.index.equals(df.index)
    assert check_time_order(df, result.labels, spec)["status"] == "pass"


def test_target_leakage_keeps_unseen_calendar_lag_evidence(panel):
    df, spec = panel
    # An ordinary three-row lag is still unseen when every observation
    # window closes in 2030. It must remain a leak under scalar offsets.
    spec.horizon = pd.DateOffset(year=2030, days=1)
    df["lag"] = df.groupby(spec.entity_col)[spec.target_col].shift(3)
    spec.feature_cols = ["lag"]
    spec.validate(df)
    labels = pd.Series("train", index=df.index)
    result = check_target_leakage(df, labels, spec)
    assert result["status"] == "fail"
    assert any(suspect["feature"] == "lag" for suspect in result["suspects"])
