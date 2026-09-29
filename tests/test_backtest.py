import numpy as np
import pandas as pd

from signals.backtest import (
    BacktestParams, bias_events, buy_and_hold_return, equity_curve,
    rolling_streak, rsi_events, simulate_trades, summarize_trades,
)
from signals.indicators import current_streak


def _ohlcv(close, index=None):
    close = pd.Series(close, dtype=float)
    if index is None:
        index = pd.bdate_range("2025-01-01", periods=len(close))
    close.index = index
    return pd.DataFrame({"Open": close, "High": close + 0.5, "Low": close - 0.5,
                         "Close": close}, index=index)


# ---------------- rolling_streak ----------------

def test_rolling_streak_matches_current_streak_at_every_prefix():
    close = pd.Series([10, 11, 12, 11, 10, 9, 9, 10, 11, 12, 13])
    streak = rolling_streak(close)
    for i in range(1, len(close)):
        assert streak.iloc[i] == current_streak(close.iloc[: i + 1]), f"mismatch at {i}"


def test_rolling_streak_flat_day_resets_to_zero():
    close = pd.Series([10.0, 11.0, 11.0, 12.0])
    streak = rolling_streak(close)
    assert streak.iloc[2] == 0          # flat day
    assert streak.iloc[3] == 1          # fresh run starts after the flat day


# ---------------- rsi_events ----------------

def test_rsi_events_oversold_and_overbought():
    idx = pd.bdate_range("2025-01-01", periods=6)
    rsi = pd.Series([50, 40, 25, 35, 75, 60], index=idx, dtype=float)
    ev = rsi_events(rsi, rsi_low=30, rsi_high=70)
    assert ev.tolist() == [0, 0, 1, 0, -1, 0]


# ---------------- bias_events ----------------

def test_bias_events_fire_only_on_state_change():
    idx = pd.bdate_range("2025-01-01", periods=6)
    df = pd.DataFrame({
        "Close": [10, 10, 10, 10, 10, 10],  # flat, so the streak bonus never kicks in
        "MACD_x": [1, 0, 0, 0, 0, -1],
        "SMA_x": [0, 0, 0, 0, 0, 0],
    }, index=idx, dtype=float)
    ev = bias_events(df, cross_cols=("MACD_x", "SMA_x"))
    # day0: score 1 -> state Bullish (prev Neutral) -> event +1
    assert ev.iloc[0] == 1
    # score drops to 0 (Neutral) on day1 and stays there until the day5 bearish signal
    assert ev.iloc[1:5].tolist() == [0, 0, 0, 0]
    assert ev.iloc[5] == -1


def test_bias_events_reenters_bullish_after_dipping_to_neutral():
    # With a rising streak building alongside a one-off MACD cross, the state
    # can dip to Neutral and then re-enter Bullish once the streak itself
    # reaches the +2 threshold - each entry into Bullish is its own event.
    idx = pd.bdate_range("2025-01-01", periods=6)
    df = pd.DataFrame({
        "Close": [10, 11, 12, 13, 12, 11],
        "MACD_x": [1, 0, 0, 0, 0, -1],
        "SMA_x": [0, 0, 0, 0, 0, 0],
    }, index=idx, dtype=float)
    ev = bias_events(df, cross_cols=("MACD_x", "SMA_x"))
    assert ev.tolist() == [1, 0, 1, 0, 0, -1]


# ---------------- simulate_trades: entry timing ----------------

def test_entry_executes_at_next_bar_open_not_signal_bar_close():
    idx = pd.bdate_range("2025-01-01", periods=5)
    df = _ohlcv([100, 100, 100, 100, 100], index=idx)
    df.loc[idx[3], "Open"] = 999  # distinctive value to prove which bar's Open is used
    events = pd.Series([0, 0, 1, 0, 0], index=idx)  # fires on bar 2 (close)
    trades = simulate_trades(df, events, BacktestParams(hold_days=1))
    assert len(trades) == 1
    assert trades.iloc[0]["entry_date"] == idx[3]
    assert trades.iloc[0]["entry_price"] == 999


# ---------------- fixed holding period ----------------

def test_fixed_holding_period_exit_long_and_short():
    idx = pd.bdate_range("2025-01-01", periods=10)
    closes = [100, 100, 100, 110, 111, 112, 113, 114, 115, 116]
    df = _ohlcv(closes, index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1  # long entry triggers at bar 2's open
    trades = simulate_trades(df, events, BacktestParams(direction="long", hold_days=3))
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["exit_reason"] == "holding_period"
    assert t["bars_held"] == 3
    assert t["direction"] == "Long"
    assert abs(t["gross_return"] - (df["Close"].iloc[2 + 3] / df["Open"].iloc[2] - 1)) < 1e-9

    events_short = pd.Series(0, index=idx)
    events_short.iloc[1] = -1
    trades_s = simulate_trades(df, events_short, BacktestParams(direction="short", hold_days=3))
    ts = trades_s.iloc[0]
    assert ts["direction"] == "Short"
    entry_p, exit_p = ts["entry_price"], ts["exit_price"]
    assert abs(ts["gross_return"] - (entry_p / exit_p - 1)) < 1e-9


# ---------------- signal-reversal exit, with hold_days as a safety cap ----------------

def test_signal_exit_fires_before_the_hold_day_cap():
    idx = pd.bdate_range("2025-01-01", periods=10)
    df = _ohlcv([100] * 10, index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1    # long entry at bar 2's open
    events.iloc[4] = -1   # opposite signal fires at bar 4's close -> exit at bar 5's open
    trades = simulate_trades(df, events, BacktestParams(direction="long", use_signal_exit=True, hold_days=50))
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["exit_reason"] == "signal_reversal"
    assert t["exit_date"] == idx[5]


def test_hold_days_caps_a_signal_that_never_reverses():
    idx = pd.bdate_range("2025-01-01", periods=10)
    df = _ohlcv([100] * 10, index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1  # long entry, never gets an opposite signal
    trades = simulate_trades(df, events, BacktestParams(direction="long", use_signal_exit=True, hold_days=3))
    assert trades.iloc[0]["exit_reason"] == "holding_period"
    assert trades.iloc[0]["bars_held"] == 3


# ---------------- stop loss ----------------

def test_stop_loss_triggers_before_holding_period_on_adverse_move():
    idx = pd.bdate_range("2025-01-01", periods=10)
    closes = [100.0] * 10
    df = _ohlcv(closes, index=idx)
    df.loc[idx[3], "Low"] = 90.0  # a sharp intraday drop on bar 3
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1  # long entry at bar 2's open (entry_price=100)
    trades = simulate_trades(df, events, BacktestParams(direction="long", hold_days=50, stop_loss_pct=0.05))
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["exit_reason"] == "stop_loss"
    assert abs(t["exit_price"] - 95.0) < 1e-9  # 5% below entry of 100


def test_stop_loss_for_short_on_adverse_rise():
    idx = pd.bdate_range("2025-01-01", periods=10)
    df = _ohlcv([100.0] * 10, index=idx)
    df.loc[idx[3], "High"] = 110.0
    events = pd.Series(0, index=idx)
    events.iloc[1] = -1  # short entry at 100
    trades = simulate_trades(df, events, BacktestParams(direction="short", hold_days=50, stop_loss_pct=0.05))
    t = trades.iloc[0]
    assert t["exit_reason"] == "stop_loss"
    assert abs(t["exit_price"] - 105.0) < 1e-9


# ---------------- no overlapping trades ----------------

def test_no_new_entry_while_a_trade_is_open():
    idx = pd.bdate_range("2025-01-01", periods=10)
    df = _ohlcv([100] * 10, index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1  # opens a trade
    events.iloc[2] = 1  # should be ignored - already in a position
    trades = simulate_trades(df, events, BacktestParams(direction="long", hold_days=3))
    assert len(trades) == 1  # not 2


def test_end_of_data_forces_a_close():
    idx = pd.bdate_range("2025-01-01", periods=5)
    df = _ohlcv([100, 100, 100, 100, 105], index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1
    trades = simulate_trades(df, events, BacktestParams(direction="long", hold_days=50))
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "end_of_data"


# ---------------- direction filtering ----------------

def test_long_only_ignores_short_entries_but_still_exits_on_opposite_signal():
    idx = pd.bdate_range("2025-01-01", periods=10)
    df = _ohlcv([100] * 10, index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1   # long entry
    events.iloc[4] = -1  # should close the long (signal exit) even though direction="long"
    trades = simulate_trades(df, events, BacktestParams(direction="long", use_signal_exit=True, hold_days=50))
    assert len(trades) == 1
    assert trades.iloc[0]["direction"] == "Long"
    assert trades.iloc[0]["exit_reason"] == "signal_reversal"

    # a bare short-only signal with no long entries should produce zero trades
    events_short_only = pd.Series(0, index=idx)
    events_short_only.iloc[1] = -1
    trades2 = simulate_trades(df, events_short_only, BacktestParams(direction="long", hold_days=3))
    assert len(trades2) == 0


# ---------------- costs ----------------

def test_cost_bps_reduces_net_return():
    idx = pd.bdate_range("2025-01-01", periods=5)
    df = _ohlcv([100, 100, 110, 110, 110], index=idx)
    events = pd.Series(0, index=idx)
    events.iloc[1] = 1
    trades = simulate_trades(df, events, BacktestParams(direction="long", hold_days=1, cost_bps=50))
    t = trades.iloc[0]
    assert abs((t["gross_return"] - t["net_return"]) - 0.005) < 1e-9


# ---------------- summary stats ----------------

def test_summarize_trades_empty_is_safe():
    idx = pd.bdate_range("2025-01-01", periods=5)
    df = _ohlcv([100, 101, 102, 103, 104], index=idx)
    empty = simulate_trades(df, pd.Series(0, index=idx), BacktestParams())
    s = summarize_trades(empty, df)
    assert s["n_trades"] == 0
    assert np.isnan(s["win_rate"])
    assert s["buy_and_hold_return"] > 0


def test_summarize_trades_matches_manual_calc():
    trades = pd.DataFrame({
        "net_return": [0.10, -0.05, 0.20],
        "bars_held": [3, 5, 2],
    })
    idx = pd.bdate_range("2025-01-01", periods=3)
    df = _ohlcv([100, 100, 100], index=idx)
    s = summarize_trades(trades, df)
    assert s["n_trades"] == 3
    assert abs(s["win_rate"] - 2 / 3) < 1e-9
    assert abs(s["avg_return"] - trades["net_return"].mean()) < 1e-9
    expected_total = (1.10 * 0.95 * 1.20) - 1
    assert abs(s["total_compounded_return"] - expected_total) < 1e-9


def test_buy_and_hold_return():
    idx = pd.bdate_range("2025-01-01", periods=3)
    df = _ohlcv([100, 100, 150], index=idx)
    assert abs(buy_and_hold_return(df) - 0.5) < 1e-9


def test_equity_curve_indexed_by_exit_date():
    trades = pd.DataFrame({
        "exit_date": pd.to_datetime(["2025-01-05", "2025-01-10"]),
        "net_return": [0.10, -0.10],
    })
    curve = equity_curve(trades)
    assert abs(curve.iloc[-1] - (1.10 * 0.90 - 1)) < 1e-9
