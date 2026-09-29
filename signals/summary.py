"""Turn per-ticker snapshots into a table, summary strings, an overall bias, and screens."""
import pandas as pd

from signals.indicators import snapshot

CROSS_COLS = ("MACD_x", "SMA_x", "CCI_x", "VWAP_x", "Support_x", "Resistance_x", "EMA_x", "SMA150_x")
# ATR_x is deliberately excluded: it flags volatility expanding/contracting, not a
# bullish/bearish direction, so it shouldn't move the net Bias score either way.


def build_table(prices: dict[str, pd.DataFrame], lookback: int = 3) -> pd.DataFrame:
    rows = {t: snapshot(df, lookback) for t, df in prices.items()}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("Ticker")


def _summarize(row, rsi_low: float, rsi_high: float) -> str:
    parts = []
    for col, label in (("MACD_x", "MACD"), ("SMA_x", "SMA10/50"), ("CCI_x", "CCI"),
                      ("VWAP_x", "VWAP"), ("EMA_x", "EMA9/18"), ("SMA150_x", "SMA150")):
        if row[col]:
            parts.append(f"{label} {'↑' if row[col] > 0 else '↓'}")
    if row["Resistance_x"] > 0:
        parts.append("resistance breakout")
    elif row["Resistance_x"] < 0:
        parts.append("back below resistance")
    if row["Support_x"] < 0:
        parts.append("support breakdown")
    elif row["Support_x"] > 0:
        parts.append("bounced off support")
    if row["ATR_x"] > 0:
        parts.append("volatility expanding")
    elif row["ATR_x"] < 0:
        parts.append("volatility contracting")
    if abs(row["Streak"]) >= 2:
        parts.append(f"{'↑' if row['Streak'] > 0 else '↓'} {abs(row['Streak'])}d streak")
    if row["RSI"] > rsi_high:
        parts.append("RSI high")
    elif row["RSI"] < rsi_low:
        parts.append("RSI low")
    return ", ".join(parts) or "–"


def _bias(row) -> str:
    """Net direction from crossover events plus any streak of 2+ days.
    Purely mechanical (counts signals, doesn't weight them) - a quick-glance
    label, not a recommendation."""
    score = sum(row[c] for c in CROSS_COLS)
    if abs(row["Streak"]) >= 2:
        score += 1 if row["Streak"] > 0 else -1
    if score > 0:
        return "Bullish"
    if score < 0:
        return "Bearish"
    return "Neutral"


def add_summary(table: pd.DataFrame, rsi_low: float, rsi_high: float) -> pd.DataFrame:
    table = table.copy()
    table["Bias"] = table.apply(_bias, axis=1)
    table["Signals"] = table.apply(_summarize, axis=1, args=(rsi_low, rsi_high))
    return table


# name -> function(table, rsi_low, rsi_high) -> boolean mask
PRESETS = {
    "All": lambda t, lo, hi: pd.Series(True, index=t.index),
    "Bullish (any signal)": lambda t, lo, hi: t["Bias"] == "Bullish",
    "Bearish (any signal)": lambda t, lo, hi: t["Bias"] == "Bearish",
    "Oversold (RSI low)": lambda t, lo, hi: t["RSI"] < lo,
    "Overbought (RSI high)": lambda t, lo, hi: t["RSI"] > hi,
    "Bullish crossover (MACD or SMA)": lambda t, lo, hi: (t["MACD_x"] > 0) | (t["SMA_x"] > 0),
    "Bearish crossover (MACD or SMA)": lambda t, lo, hi: (t["MACD_x"] < 0) | (t["SMA_x"] < 0),
    "Resistance breakout": lambda t, lo, hi: t["Resistance_x"] > 0,
    "Support breakdown": lambda t, lo, hi: t["Support_x"] < 0,
    "EMA 9/18 bullish cross": lambda t, lo, hi: t["EMA_x"] > 0,
    "EMA 9/18 bearish cross": lambda t, lo, hi: t["EMA_x"] < 0,
    "Crossed above SMA150": lambda t, lo, hi: t["SMA150_x"] > 0,
    "Crossed below SMA150": lambda t, lo, hi: t["SMA150_x"] < 0,
    "Volatility expanding (ATR)": lambda t, lo, hi: t["ATR_x"] > 0,
    "Uptrend pullback (above SMA200, RSI low)": lambda t, lo, hi: t["Above_SMA200"] & (t["RSI"] < lo),
}
