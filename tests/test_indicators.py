import numpy as np
import pandas as pd

from signals.indicators import compute_indicators, cross_events, current_streak, rsi, snapshot


def _ohlcv(close):
    close = pd.Series(close, index=pd.bdate_range("2025-01-01", periods=len(close)), dtype=float)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1,
                         "Close": close, "Volume": 1000.0})


def test_rsi_monotonic_up_is_100():
    assert rsi(pd.Series(np.arange(1.0, 60.0))).iloc[-1] == 100


def test_rsi_bounds():
    r = rsi(pd.Series(np.random.default_rng(0).normal(100, 2, 300).cumsum())).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_cross_events_detects_and_ignores_warmup():
    a = pd.Series([np.nan, 1, 1, 3, 3, 0])
    b = pd.Series([np.nan, 2, 2, 2, 2, 2])
    assert cross_events(a, b).tolist() == [0, 0, 0, 1, 0, -1]


def test_streak():
    assert current_streak(pd.Series([5, 4, 3, 4, 5, 6])) == 3
    assert current_streak(pd.Series([1, 2, 3, 2, 1])) == -2
    assert current_streak(pd.Series([1, 1])) == 0


def test_sma_matches_manual():
    df = compute_indicators(_ohlcv(range(1, 101)))
    assert df["SMA_10"].iloc[-1] == np.mean(range(91, 101))


def test_flat_prices_give_zero_macd():
    df = compute_indicators(_ohlcv([50] * 120))
    assert df["MACD"].abs().max() < 1e-9


def test_snapshot_keys_and_streak():
    s = snapshot(_ohlcv(range(1, 260)), lookback=3)
    assert s["Streak"] == 258 and s["Above_SMA200"] is True
    assert s["From_52w_High"] < 0.01 and s["RSI"] == 100


def test_resistance_breakout_on_new_high():
    # Flat at 100 for 40 days, then a sharp jump: today's close should be
    # flagged as a resistance breakout (using the *prior* 20-day high, not today's).
    closes = [100.0] * 40 + [110.0]
    df = compute_indicators(_ohlcv(closes))
    assert df["Resistance"].iloc[-1] == 101.0  # prior day's high (100 + 1), shifted
    assert df["Resistance_x"].iloc[-1] == 1


def test_support_breakdown_on_sharp_drop():
    closes = [100.0] * 40 + [90.0]
    df = compute_indicators(_ohlcv(closes))
    assert df["Support"].iloc[-1] == 99.0  # prior day's low (100 - 1), shifted
    assert df["Support_x"].iloc[-1] == -1


def test_vwap_close_to_price_when_flat():
    df = compute_indicators(_ohlcv([50.0] * 60))
    assert abs(df["VWAP"].iloc[-1] - 50.0) < 1e-9


def test_vwap_between_recent_high_and_low_on_trend():
    df = compute_indicators(_ohlcv(range(1, 101)))
    last = df.iloc[-1]
    assert df["Low"].iloc[-20:].min() <= last["VWAP"] <= df["High"].iloc[-20:].max()


def test_snapshot_includes_new_fields():
    s = snapshot(_ohlcv(list(range(1, 41)) + [55]), lookback=3)
    for key in ("Support", "Resistance", "VWAP", "Support_x", "Resistance_x", "VWAP_x"):
        assert key in s
    assert s["Resistance_x"] == 1  # the jump to 55 breaks above the prior range
