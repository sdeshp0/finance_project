from datetime import date, datetime, timezone

import pandas as pd
import pytest

from signals.data_core import last_trading_day, slice_snapshot, snapshot_is_fresh


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize("now, expected", [
    # Tue 2026-10-13, EDT (UTC-4): close is 20:00 UTC
    (_utc(2026, 10, 13, 19, 59), date(2026, 10, 12)),  # before close -> Monday
    (_utc(2026, 10, 13, 20, 0), date(2026, 10, 13)),   # at close -> Tuesday
    (_utc(2026, 10, 14, 1, 0), date(2026, 10, 13)),    # Tue evening ET, Wed in UTC
    (_utc(2026, 10, 12, 15, 0), date(2026, 10, 9)),    # Mon before close -> Friday
    (_utc(2026, 10, 10, 18, 0), date(2026, 10, 9)),    # Saturday -> Friday
    (_utc(2026, 10, 11, 23, 0), date(2026, 10, 9)),    # Sunday -> Friday
    # December, EST (UTC-5): close is 21:00 UTC
    (_utc(2026, 12, 15, 20, 30), date(2026, 12, 14)),
    (_utc(2026, 12, 15, 21, 0), date(2026, 12, 15)),
])
def test_last_trading_day(now, expected):
    assert last_trading_day(now) == expected


def test_snapshot_is_fresh():
    now = _utc(2026, 10, 14, 15, 0)  # Wed, market open -> Tuesday's close is the latest
    assert snapshot_is_fresh(date(2026, 10, 13), now)
    assert not snapshot_is_fresh(date(2026, 10, 12), now)


def _wide(tickers, n=300):
    idx = pd.bdate_range(end="2026-10-13", periods=n)
    frames = {t: pd.DataFrame({f: 1.0 for f in ["Open", "High", "Low", "Close", "Volume"]},
                              index=idx) for t in tickers}
    return pd.concat(frames, axis=1)


def test_slice_snapshot_splits_present_and_missing():
    prices, missing = slice_snapshot(_wide(["AAA", "BBB"]), ("AAA", "ZZZ"), "1y")
    assert list(prices) == ["AAA"]
    assert missing == ["ZZZ"]
    assert list(prices["AAA"].columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_slice_snapshot_trims_to_period():
    wide = _wide(["AAA"])
    six, _ = slice_snapshot(wide, ("AAA",), "6mo")
    year, _ = slice_snapshot(wide, ("AAA",), "1y")
    assert six["AAA"].index.min() > pd.Timestamp("2026-04-13")
    assert year["AAA"].index.min() > pd.Timestamp("2025-10-13")
    assert len(six["AAA"]) < len(year["AAA"]) < len(wide)


def test_slice_snapshot_treats_short_history_as_missing():
    wide = _wide(["AAA", "NEW"])
    wide.loc[wide.index[:-10], ("NEW", "Close")] = float("nan")  # only 10 bars of data
    prices, missing = slice_snapshot(wide, ("AAA", "NEW"), "1y")
    assert list(prices) == ["AAA"]
    assert missing == ["NEW"]
