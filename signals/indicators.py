"""Technical indicators. Pure pandas/numpy (no Streamlit), pandas-3 safe."""
import numpy as np
import pandas as pd

SMA_WINDOWS = (10, 50, 100, 200)
SR_WINDOW = 20     # support/resistance lookback (Donchian-style channel)
VWAP_WINDOW = 20   # rolling VWAP window (daily bars only -> approximation, not intraday VWAP)


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI (exponential smoothing, alpha = 1/n)."""
    d = close.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    avg_up = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_dn = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + avg_up / avg_dn)


def cross_events(a: pd.Series, b: pd.Series) -> pd.Series:
    """+1 where a crosses above b, -1 where it crosses below, else 0.
    Ignores warm-up rows where either series is NaN."""
    valid = a.notna() & b.notna()
    ev = (a > b).astype(int).diff()
    ok = valid & valid.shift(1, fill_value=False)
    return ev.where(ok, 0).fillna(0).astype(int)


def current_streak(close: pd.Series) -> int:
    """Consecutive up (+n) or down (-n) closes ending at the last bar."""
    d = np.sign(close.diff().dropna().to_numpy())
    if len(d) == 0 or d[-1] == 0:
        return 0
    n = 0
    for x in d[::-1]:
        if x != d[-1]:
            break
        n += 1
    return int(n * d[-1])


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """df: OHLCV indexed by date. Returns a copy with indicator columns added."""
    df = df.copy()
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

    for n in SMA_WINDOWS:
        df[f"SMA_{n}"] = c.rolling(n).mean()
    df["RSI"] = rsi(c)

    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["MACD"] = macd
    df["MACD_signal"] = macd.ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    tp = (h + l + c) / 3
    mean_dev = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["CCI"] = (tp - tp.rolling(20).mean()) / (0.015 * mean_dev)

    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    df["CMF"] = (mfm * v).rolling(20).sum() / v.rolling(20).sum()
    df["Vol_Index"] = v / v.rolling(50).mean()
    df["High_52w"] = h.rolling(252, min_periods=1).max()

    # Support / resistance: prior SR_WINDOW bars' low/high (shifted so today's own
    # bar isn't part of its own level -> a close above resistance is a real breakout).
    df["Resistance"] = h.shift(1).rolling(SR_WINDOW).max()
    df["Support"] = l.shift(1).rolling(SR_WINDOW).min()

    # Rolling VWAP (approximation): true VWAP resets intraday, but with daily bars
    # this is a volume-weighted average of the typical price over VWAP_WINDOW days.
    pv = tp * v
    df["VWAP"] = pv.rolling(VWAP_WINDOW).sum() / v.rolling(VWAP_WINDOW).sum()

    df["MACD_x"] = cross_events(df["MACD"], df["MACD_signal"])
    df["SMA_x"] = cross_events(df["SMA_10"], df["SMA_50"])
    df["CCI_x"] = cross_events(df["CCI"], pd.Series(0.0, index=df.index))
    df["Resistance_x"] = cross_events(c, df["Resistance"])
    df["Support_x"] = cross_events(c, df["Support"])
    df["VWAP_x"] = cross_events(c, df["VWAP"])
    return df


def snapshot(df: pd.DataFrame, lookback: int = 3) -> dict:
    """One row of latest values. Crossovers report the most recent cross
    within the last `lookback` bars (0 = none)."""
    x = compute_indicators(df)
    last, close = x.iloc[-1], x["Close"]

    def ret(n):
        return float(close.iloc[-1] / close.iloc[-1 - n] - 1) if len(close) > n else np.nan

    def recent(col):
        w = x[col].iloc[-lookback:]
        nz = w[w != 0]
        return int(nz.iloc[-1]) if len(nz) else 0

    return {
        "Date": x.index[-1],
        "Close": float(last["Close"]),
        "Ret_1d": ret(1), "Ret_5d": ret(5), "Ret_1m": ret(21),
        "RSI": float(last["RSI"]),
        "Vol_Index": float(last["Vol_Index"]),
        "From_52w_High": float(last["Close"] / last["High_52w"] - 1),
        "Above_SMA200": bool(last["Close"] > last["SMA_200"]),
        "Support": float(last["Support"]) if pd.notna(last["Support"]) else np.nan,
        "Resistance": float(last["Resistance"]) if pd.notna(last["Resistance"]) else np.nan,
        "VWAP": float(last["VWAP"]) if pd.notna(last["VWAP"]) else np.nan,
        "MACD_x": recent("MACD_x"), "SMA_x": recent("SMA_x"), "CCI_x": recent("CCI_x"),
        "Support_x": recent("Support_x"), "Resistance_x": recent("Resistance_x"),
        "VWAP_x": recent("VWAP_x"),
        "Streak": current_streak(close),
    }
