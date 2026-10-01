import numpy as np
import pandas as pd

from signals.indicators import beta, compute_indicators, cross_events, current_streak, rsi, snapshot
from signals.summary import CROSS_COLS, add_sector_relative_beta


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


def test_sma_150_needs_enough_bars():
    df = compute_indicators(_ohlcv(range(1, 201)))
    assert df["SMA_150"].iloc[-1] == np.mean(range(51, 201))
    assert pd.isna(df["SMA_150"].iloc[100])  # fewer than 150 bars so far


def test_ema_flat_equals_price():
    df = compute_indicators(_ohlcv([50.0] * 60))
    assert df["EMA_9"].iloc[-1] == 50.0
    assert df["EMA_18"].iloc[-1] == 50.0


def test_atr_converges_to_constant_true_range():
    # For this fixture (High=Close+1, Low=Close-1, Close rising by 1/day),
    # every day's true range works out to exactly 2, so ATR should converge to 2.
    df = compute_indicators(_ohlcv(range(1, 101)))
    assert abs(df["ATR"].iloc[-1] - 2.0) < 1e-9


def test_ema_crossover_detects_fast_over_slow():
    # A sharp jump should pull the fast EMA9 above the slower EMA18.
    closes = [50.0] * 60 + [70.0] * 5
    df = compute_indicators(_ohlcv(closes))
    assert (df["EMA_x"].iloc[-5:] == 1).any()


def test_price_crosses_above_sma150():
    closes = [50.0] * 160 + [80.0]
    df = compute_indicators(_ohlcv(closes))
    assert df["SMA150_x"].iloc[-1] == 1


def test_atr_expansion_flagged_after_volatility_jump():
    # Long calm stretch (small constant range) then a sudden much wider range:
    # ATR should cross above its own 20-day average.
    calm = [100.0 + 0.01 * i for i in range(60)]
    df = compute_indicators(_ohlcv(calm))
    df.loc[df.index[-1], ["High", "Low"]] = [130.0, 70.0]  # manual volatility spike
    # recompute ATR/ATR_SMA/ATR_x on the modified frame
    from signals.indicators import cross_events
    prev_close = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - prev_close).abs(),
                   (df["Low"] - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    atr_sma = atr.rolling(20).mean()
    x = cross_events(atr, atr_sma)
    assert x.iloc[-1] == 1


def test_snapshot_includes_all_new_cross_fields():
    s = snapshot(_ohlcv([50.0] * 60 + [70.0] * 5), lookback=3)
    for key in ("EMA_x", "SMA150_x", "ATR_x", "SMA_150", "ATR"):
        assert key in s


def test_beta_recovers_known_value():
    idx = pd.bdate_range("2024-01-01", periods=300)
    rng = np.random.default_rng(3)
    bench_ret = rng.normal(0, 0.01, 300)
    true_beta = 1.5
    stock_ret = true_beta * bench_ret + rng.normal(0, 0.005, 300)
    bench_close = pd.Series(100 * np.cumprod(1 + bench_ret), index=idx)
    stock_close = pd.Series(100 * np.cumprod(1 + stock_ret), index=idx)
    b = beta(stock_close, bench_close, window=252)
    assert abs(b - true_beta) < 0.15


def test_self_beta_is_one():
    idx = pd.bdate_range("2024-01-01", periods=300)
    close = pd.Series(100 + np.random.default_rng(1).normal(0, 1, 300).cumsum(), index=idx)
    assert abs(beta(close, close) - 1.0) < 1e-9


def test_beta_nan_on_insufficient_overlap():
    idx = pd.bdate_range("2024-01-01", periods=10)
    close = pd.Series(np.arange(100, 110), index=idx, dtype=float)
    assert np.isnan(beta(close, close, window=252, min_periods=40))


def test_snapshot_beta_key_present_and_nan_without_benchmark():
    s = snapshot(_ohlcv(range(1, 60)), lookback=3)
    assert "Beta" in s and np.isnan(s["Beta"])


def test_snapshot_beta_populated_with_benchmark():
    idx = pd.bdate_range("2024-01-01", periods=300)
    rng = np.random.default_rng(5)
    bench_ret = rng.normal(0, 0.01, 300)
    bench_close = pd.Series(100 * np.cumprod(1 + bench_ret), index=idx)
    stock_close = pd.Series(100 * np.cumprod(1 + 1.2 * bench_ret + rng.normal(0, 0.003, 300)), index=idx)
    df = pd.DataFrame({"Open": stock_close, "High": stock_close + 1, "Low": stock_close - 1,
                       "Close": stock_close, "Volume": 1000.0}, index=idx)
    s = snapshot(df, lookback=3, benchmark_close=bench_close)
    assert not np.isnan(s["Beta"])
    assert 0.9 < s["Beta"] < 1.5


def test_sector_relative_beta_leave_one_out():
    table = pd.DataFrame({
        "Beta": [1.0, 1.5, 2.0, 1.2, 0.5, 0.6],
        "GICS Sector": ["Tech", "Tech", "Tech", "Tech", "Utilities", "Utilities"],
    }, index=["A", "B", "C", "D", "E", "F"])
    out = add_sector_relative_beta(table, min_peers=3)

    expected_a_avg = (1.5 + 2.0 + 1.2) / 3  # A's own beta excluded
    assert abs(out.loc["A", "Sector Beta"] - expected_a_avg) < 1e-9
    assert abs(out.loc["A", "Beta vs Sector"] - (1.0 / expected_a_avg)) < 1e-9

    # Utilities only has 2 tickers -> 1 peer left after excluding self -> below min_peers
    assert np.isnan(out.loc["E", "Sector Beta"])
    assert np.isnan(out.loc["F", "Beta vs Sector"])


def test_sector_relative_beta_handles_missing_own_beta():
    table = pd.DataFrame({
        "Beta": [1.0, 1.5, 2.0, 1.2, np.nan],
        "GICS Sector": ["Tech"] * 5,
    }, index=["A", "B", "C", "D", "E"])
    out = add_sector_relative_beta(table, min_peers=3)
    expected_e_avg = (1.0 + 1.5 + 2.0 + 1.2) / 4  # nothing of E's own to exclude
    assert abs(out.loc["E", "Sector Beta"] - expected_e_avg) < 1e-9
    assert np.isnan(out.loc["E", "Beta vs Sector"])  # no own beta to form a ratio with


def test_sector_relative_beta_without_sector_column_is_safe():
    table = pd.DataFrame({"Beta": [1.0, 1.2]}, index=["X", "Y"])
    out = add_sector_relative_beta(table)
    assert out["Sector Beta"].isna().all()
    assert out["Beta vs Sector"].isna().all()


def test_cmf_crosses_zero_from_buying_to_selling_pressure():
    # Up-leg: close sits near the top of each day's range (buying pressure ->
    # positive CMF). Down-leg: close sits near the bottom (selling pressure ->
    # negative CMF). Symmetric High/Low around Close would make the money-flow
    # multiplier exactly zero regardless of trend, so the range has to be skewed.
    n_up, n_down = 40, 20
    closes = list(range(100, 100 + n_up)) + list(range(100 + n_up, 100 + n_up - n_down, -1))
    idx = pd.bdate_range("2025-01-01", periods=len(closes))
    close = pd.Series(closes, index=idx, dtype=float)
    high = close.copy()
    low = close.copy()
    high.iloc[:n_up] = close.iloc[:n_up] + 0.2   # up-leg: close near the high
    low.iloc[:n_up] = close.iloc[:n_up] - 2.0
    high.iloc[n_up:] = close.iloc[n_up:] + 2.0    # down-leg: close near the low
    low.iloc[n_up:] = close.iloc[n_up:] - 0.2
    df = pd.DataFrame({
        "Open": close, "High": high, "Low": low, "Close": close, "Volume": 1_000_000.0,
    }, index=idx)
    out = compute_indicators(df)
    assert out["CMF"].iloc[n_up - 5] > 0           # well into the up-leg: positive
    assert out["CMF"].iloc[-5] < 0                 # well into the down-leg: negative
    assert (out["CMF_x"] == -1).any()              # a bearish zero-cross happened somewhere


def test_cmf_in_cross_cols_and_bias():
    assert "CMF_x" in CROSS_COLS
