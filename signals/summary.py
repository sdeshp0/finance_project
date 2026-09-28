"""Turn per-ticker snapshots into a table, summary strings and screening presets."""
import pandas as pd

from signals.indicators import snapshot


def build_table(prices: dict[str, pd.DataFrame], lookback: int = 3) -> pd.DataFrame:
    rows = {t: snapshot(df, lookback) for t, df in prices.items()}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("Ticker")


def _summarize(row, rsi_low: float, rsi_high: float) -> str:
    parts = []
    for col, label in (("MACD_x", "MACD"), ("SMA_x", "SMA10/50"), ("CCI_x", "CCI")):
        if row[col]:
            parts.append(f"{label} {'↑' if row[col] > 0 else '↓'}")
    if abs(row["Streak"]) >= 2:
        parts.append(f"{'↑' if row['Streak'] > 0 else '↓'} {abs(row['Streak'])}d streak")
    if row["RSI"] > rsi_high:
        parts.append("RSI high")
    elif row["RSI"] < rsi_low:
        parts.append("RSI low")
    return ", ".join(parts) or "–"


def add_summary(table: pd.DataFrame, rsi_low: float, rsi_high: float) -> pd.DataFrame:
    table = table.copy()
    table["Signals"] = table.apply(_summarize, axis=1, args=(rsi_low, rsi_high))
    return table


# name -> function(table, rsi_low, rsi_high) -> boolean mask
PRESETS = {
    "All": lambda t, lo, hi: pd.Series(True, index=t.index),
    "Oversold (RSI low)": lambda t, lo, hi: t["RSI"] < lo,
    "Overbought (RSI high)": lambda t, lo, hi: t["RSI"] > hi,
    "Bullish crossover (MACD or SMA)": lambda t, lo, hi: (t["MACD_x"] > 0) | (t["SMA_x"] > 0),
    "Bearish crossover (MACD or SMA)": lambda t, lo, hi: (t["MACD_x"] < 0) | (t["SMA_x"] < 0),
    "Uptrend pullback (above SMA200, RSI low)": lambda t, lo, hi: t["Above_SMA200"] & (t["RSI"] < lo),
}
