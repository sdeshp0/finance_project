from datetime import date, datetime, timezone

import pandas as pd
import pytest

from signals import data_core
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


class _Resp:
    def __init__(self, content: bytes, status: int = 200):
        self.content, self.status = content, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


def _fake_get(files: dict[str, bytes], fail: str | None = None):
    def get(url, **kwargs):
        name = url.rsplit("/", 1)[1]
        return _Resp(b"", 404) if name == fail else _Resp(files[name])
    return get


PUBLISHED = {
    "snapshot_meta.json": b'{"as_of": "2026-10-17"}',
    "snapshot_constituents.csv": b"Ticker\nAAPL\n",
    "snapshot_prices.parquet": b"parquet-bytes",
}


def test_download_snapshot_writes_all_files(tmp_path, monkeypatch):
    monkeypatch.setattr(data_core.requests, "get", _fake_get(PUBLISHED))
    assert data_core.download_snapshot(tmp_path / "data", base_url="https://x") is True
    assert {p.name: p.read_bytes() for p in (tmp_path / "data").iterdir()} == PUBLISHED


def test_download_snapshot_skips_when_meta_unchanged(tmp_path, monkeypatch):
    (tmp_path / "snapshot_meta.json").write_bytes(PUBLISHED["snapshot_meta.json"])
    monkeypatch.setattr(data_core.requests, "get", _fake_get(PUBLISHED))
    assert data_core.download_snapshot(tmp_path, base_url="https://x") is False
    assert [p.name for p in tmp_path.iterdir()] == ["snapshot_meta.json"]


def test_download_snapshot_failure_keeps_old_files(tmp_path, monkeypatch):
    old = {name: b"old" for name in PUBLISHED}
    for name, content in old.items():
        (tmp_path / name).write_bytes(content)
    monkeypatch.setattr(data_core.requests, "get",
                        _fake_get(PUBLISHED, fail="snapshot_prices.parquet"))
    with pytest.raises(RuntimeError):
        data_core.download_snapshot(tmp_path, base_url="https://x")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == old
