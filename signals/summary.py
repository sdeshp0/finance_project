"""Turn per-ticker snapshots into a table, summary strings, an overall bias, and screens."""
import numpy as np
import pandas as pd

from signals.indicators import snapshot

CROSS_COLS = ("MACD_x", "SMA_x", "CCI_x", "VWAP_x", "Support_x", "Resistance_x", "EMA_x", "SMA150_x")
# ATR_x is deliberately excluded: it flags volatility expanding/contracting, not a
# bullish/bearish direction, so it shouldn't move the net Bias score either way.


def build_table(prices: dict[str, pd.DataFrame], lookback: int = 3,
                benchmark_close: pd.Series | None = None) -> pd.DataFrame:
    rows = {t: snapshot(df, lookback, benchmark_close) for t, df in prices.items()}
    return pd.DataFrame.from_dict(rows, orient="index").rename_axis("Ticker")


def add_sector_relative_beta(table: pd.DataFrame, sector_col: str = "GICS Sector",
                             min_peers: int = 3) -> pd.DataFrame:
    """Adds 'Sector Beta' (the sector peer group's average Beta) and 'Beta vs
    Sector' (this ticker's Beta divided by that average) - a peer-relative
    read on beta, not just a market-relative one.

    The peer average is leave-one-out: a ticker's own Beta is excluded from
    its own comparison group, so it can't dominate a small sample. It also
    only uses whichever sector peers are currently loaded in the app (not the
    full 500), and requires at least `min_peers` *other* tickers with a valid
    Beta in the same sector before showing a comparison - below that, both
    new columns are NaN rather than a noisy ratio from a near-empty group.

    If `sector_col` isn't present at all (e.g. a custom, non-sector ticker
    list has no sector info to compare against), both columns are added as
    all-NaN rather than raising.
    """
    table = table.copy()
    if sector_col not in table.columns or "Beta" not in table.columns:
        table["Sector Beta"] = np.nan
        table["Beta vs Sector"] = np.nan
        return table

    grp = table.groupby(sector_col)["Beta"]
    sector_n = grp.transform("count")     # non-NaN Betas in the sector (pandas count skips NaN)
    sector_sum = grp.transform("sum")     # sum of non-NaN Betas in the sector

    has_own = table["Beta"].notna()
    loo_sum = sector_sum - table["Beta"].fillna(0)
    loo_n = sector_n - has_own.astype(int)

    sector_avg = loo_sum / loo_n.replace(0, np.nan)
    sector_avg = sector_avg.where(loo_n >= min_peers)

    table["Sector Beta"] = sector_avg
    table["Beta vs Sector"] = table["Beta"] / sector_avg.replace(0, np.nan)
    return table


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

# Groups the presets for a two-level "category -> screen" dropdown in the UI,
# instead of one long flat list. Every PRESETS key must appear exactly once
# below; the assertion catches a new preset that was added without a group.
GROUPS: dict[str, list[str]] = {
    "Overall": ["All", "Bullish (any signal)", "Bearish (any signal)"],
    "RSI": ["Oversold (RSI low)", "Overbought (RSI high)"],
    "Trend crossovers": [
        "Bullish crossover (MACD or SMA)", "Bearish crossover (MACD or SMA)",
        "EMA 9/18 bullish cross", "EMA 9/18 bearish cross",
        "Crossed above SMA150", "Crossed below SMA150",
    ],
    "Price levels": ["Resistance breakout", "Support breakdown"],
    "Volatility": ["Volatility expanding (ATR)"],
    "Combo screens": ["Uptrend pullback (above SMA200, RSI low)"],
}

assert sorted(name for names in GROUPS.values() for name in names) == sorted(PRESETS), (
    "GROUPS must list every PRESETS key exactly once - update GROUPS alongside PRESETS."
)
