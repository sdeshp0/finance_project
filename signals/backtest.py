"""Event-based backtesting for a single ticker's computed signals.

Every signal fed into the engine reduces to the same shape: a series aligned
to the ticker's OHLCV index where +1 marks a bullish/long entry trigger on
that bar, -1 marks a bearish/short entry trigger, and 0 means nothing fired.
The engine doesn't know or care which indicator produced the event -
crossovers, RSI mean-reversion, and the overall Bias score are all converted
to this shape before backtesting, so one engine handles all of them.

Entries always execute at the NEXT bar's open after the event bar's close,
since that's the earliest point a signal observed at today's close could
actually be acted on - using today's own close would be look-ahead bias.

This is a single-ticker, no-transaction-cost-by-default historical
simulation, not a validated trading system. Small sample sizes and
freely-tunable thresholds elsewhere in the app make it easy to overfit a
backtest without realizing it - see the caveats surfaced in the app UI.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from signals.indicators import cross_events
from signals.summary import CROSS_COLS

# User-facing label -> already-computed crossover event column.
# ATR_x is deliberately excluded: it's a volatility-expansion flag, not a
# directional long/short trigger, so it doesn't fit this engine's shape.
SIGNAL_COLUMNS = {
    "MACD": "MACD_x", "SMA 10/50": "SMA_x", "CCI": "CCI_x", "VWAP": "VWAP_x",
    "Support": "Support_x", "Resistance": "Resistance_x",
    "EMA 9/18": "EMA_x", "SMA150": "SMA150_x",
}

SIGNAL_GROUPS = {
    "Crossovers": list(SIGNAL_COLUMNS),
    "Mean reversion": ["RSI mean-reversion"],
    "Composite": ["Overall Bias"],
}


def rolling_streak(close: pd.Series) -> pd.Series:
    """Per-day version of indicators.current_streak: the signed consecutive
    up/down streak ending at each bar (0 on a flat day or the first bar)."""
    sign = np.sign(close.diff())
    group = (sign != sign.shift()).cumsum()
    run_len = sign.groupby(group).cumcount() + 1
    streak = np.where(sign.isna() | (sign == 0), 0, run_len * sign)
    return pd.Series(streak, index=close.index)


def rsi_events(rsi: pd.Series, rsi_low: float, rsi_high: float) -> pd.Series:
    """+1 when RSI crosses below the oversold line (mean-reversion long entry),
    -1 when RSI crosses above the overbought line (short entry)."""
    low_line = pd.Series(rsi_low, index=rsi.index)
    high_line = pd.Series(rsi_high, index=rsi.index)
    oversold_cross = cross_events(rsi, low_line)     # -1 = crossed below low
    overbought_cross = cross_events(rsi, high_line)  # +1 = crossed above high
    ev = pd.Series(0, index=rsi.index)
    ev[oversold_cross == -1] = 1
    ev[overbought_cross == 1] = -1
    return ev.astype(int)


def bias_events(df: pd.DataFrame, cross_cols: tuple = CROSS_COLS) -> pd.Series:
    """Daily net-bias state (same scoring as signals.summary._bias, computed
    for every day instead of just the latest bar), converted to an entry
    event on the day the state changes into Bullish or Bearish."""
    score = sum(df[c] for c in cross_cols)
    streak = rolling_streak(df["Close"])
    score = score + np.where(streak >= 2, 1, np.where(streak <= -2, -1, 0))
    state = pd.Series(np.sign(score), index=df.index)
    prev = state.shift(1).fillna(0)
    ev = pd.Series(0, index=df.index)
    ev[(state == 1) & (prev != 1)] = 1
    ev[(state == -1) & (prev != -1)] = -1
    return ev.astype(int)


def get_signal_events(label: str, df: pd.DataFrame, rsi_low: float, rsi_high: float) -> pd.Series:
    if label in SIGNAL_COLUMNS:
        return df[SIGNAL_COLUMNS[label]]
    if label == "RSI mean-reversion":
        return rsi_events(df["RSI"], rsi_low, rsi_high)
    if label == "Overall Bias":
        return bias_events(df)
    raise ValueError(f"Unknown signal: {label}")


@dataclass
class BacktestParams:
    direction: str = "both"       # "long", "short", or "both"
    use_signal_exit: bool = False  # also exit on the opposite event firing
    hold_days: int = 10           # fixed exit duration, AND a max-hold cap when use_signal_exit
    stop_loss_pct: float = 0.0    # 0 disables; e.g. 0.05 = 5% adverse move
    cost_bps: float = 0.0         # round-trip cost, in basis points, applied per trade


def simulate_trades(df: pd.DataFrame, events: pd.Series, params: BacktestParams) -> pd.DataFrame:
    """Walks the bars in order, opening/closing at most one position at a
    time. Returns a DataFrame of completed trades (possibly empty)."""
    idx = df.index
    o, h, l, c = df["Open"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    ev = events.reindex(idx).fillna(0).to_numpy()
    n = len(df)

    allow_long = params.direction in ("long", "both")
    allow_short = params.direction in ("short", "both")

    trades = []
    pos = None  # dict while a trade is open

    for i in range(1, n):
        if pos is None:
            trig = ev[i - 1]
            if trig == 1 and allow_long:
                pos = {"dir": 1, "entry_i": i, "entry_price": o[i]}
            elif trig == -1 and allow_short:
                pos = {"dir": -1, "entry_i": i, "entry_price": o[i]}
            continue

        bars_held = i - pos["entry_i"]
        exit_price, exit_reason = None, None

        if params.stop_loss_pct > 0:
            if pos["dir"] == 1:
                stop_price = pos["entry_price"] * (1 - params.stop_loss_pct)
                if l[i] <= stop_price:
                    exit_price, exit_reason = stop_price, "stop_loss"
            else:
                stop_price = pos["entry_price"] * (1 + params.stop_loss_pct)
                if h[i] >= stop_price:
                    exit_price, exit_reason = stop_price, "stop_loss"

        if exit_price is None and params.use_signal_exit and ev[i - 1] == -pos["dir"]:
            exit_price, exit_reason = o[i], "signal_reversal"

        if exit_price is None and bars_held >= params.hold_days:
            exit_price, exit_reason = c[i], "holding_period"

        if exit_price is not None:
            trades.append(_make_trade(idx, pos, i, exit_price, exit_reason, params.cost_bps))
            pos = None

    if pos is not None:  # still open when the data runs out
        trades.append(_make_trade(idx, pos, n - 1, c[n - 1], "end_of_data", params.cost_bps))

    cols = ["entry_date", "exit_date", "direction", "entry_price", "exit_price",
           "bars_held", "exit_reason", "gross_return", "net_return"]
    return pd.DataFrame(trades, columns=cols)


def _make_trade(idx, pos, exit_i, exit_price, exit_reason, cost_bps):
    d = pos["dir"]
    entry_price = pos["entry_price"]
    gross = (exit_price / entry_price - 1) if d == 1 else (entry_price / exit_price - 1)
    net = gross - cost_bps / 10_000
    return {
        "entry_date": idx[pos["entry_i"]], "exit_date": idx[exit_i],
        "direction": "Long" if d == 1 else "Short",
        "entry_price": entry_price, "exit_price": exit_price,
        "bars_held": exit_i - pos["entry_i"], "exit_reason": exit_reason,
        "gross_return": gross, "net_return": net,
    }


def buy_and_hold_return(df: pd.DataFrame) -> float:
    return float(df["Close"].iloc[-1] / df["Close"].iloc[0] - 1)


def summarize_trades(trades: pd.DataFrame, df: pd.DataFrame) -> dict:
    """Summary stats for the trade log, plus a buy-and-hold return over the
    same full period for reference. Safe to call on an empty trades frame."""
    n = len(trades)
    summary = {
        "n_trades": n,
        "win_rate": np.nan,
        "avg_return": np.nan,
        "median_return": np.nan,
        "total_compounded_return": np.nan,
        "max_drawdown": np.nan,
        "avg_bars_held": np.nan,
        "buy_and_hold_return": buy_and_hold_return(df),
    }
    if n == 0:
        return summary

    r = trades["net_return"]
    equity = (1 + r).cumprod()
    drawdown = equity / equity.cummax() - 1

    summary.update({
        "win_rate": float((r > 0).mean()),
        "avg_return": float(r.mean()),
        "median_return": float(r.median()),
        "total_compounded_return": float(equity.iloc[-1] - 1),
        "max_drawdown": float(drawdown.min()),
        "avg_bars_held": float(trades["bars_held"].mean()),
    })
    return summary


def equity_curve(trades: pd.DataFrame) -> pd.Series:
    """Cumulative return after each trade, indexed by exit date. This steps
    only on trade exits (not every calendar day), so it isn't directly on the
    same time axis as a continuously-held buy-and-hold curve - see the caption
    in the UI."""
    if trades.empty:
        return pd.Series(dtype=float)
    return (1 + trades.set_index("exit_date")["net_return"]).cumprod() - 1
