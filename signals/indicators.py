"""Technical indicators. Pure pandas/numpy (no Streamlit), pandas-3 safe."""
import numpy as np
import pandas as pd

SMA_WINDOWS = (10, 50, 100, 150, 200)
EMA_SPANS = (9, 18)
ATR_WINDOW = 14
ATR_SIGNAL_WINDOW = 20  # ATR's own moving average, for a volatility-expansion cross
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


def _run_length(hit: pd.Series, level: pd.Series) -> float:
    """Consecutive True values of `hit` ending at the last bar; NaN if `level`
    isn't available yet on the last bar (e.g. SMA warm-up)."""
    if len(hit) == 0 or pd.isna(level.iloc[-1]):
        return np.nan
    n = 0
    for x in hit.to_numpy()[::-1]:
        if not x:
            break
        n += 1
    return float(n)


def days_above(close: pd.Series, level: pd.Series) -> float:
    """Consecutive bars, ending at the last bar, where close > level.
    0 if the last close is at/below the level; NaN if the level isn't available
    yet on the last bar (e.g. SMA warm-up). The count also stops at the first
    bar where the level is NaN, so it can't exceed the bars since warm-up ended."""
    return _run_length(close > level, level)  # NaN level compares False -> ends the run


def days_below(close: pd.Series, level: pd.Series) -> float:
    """Mirror of days_above: consecutive bars ending at the last bar where close < level."""
    return _run_length(close < level, level)


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    """Heikin Ashi candles from OHLC. HA close is the bar's OHLC average; HA open is
    the midpoint of the previous HA candle's body (seeded from the first real bar's
    open/close midpoint), so it's recursive and settles within a few bars of the seed.
    HA high/low extend the real high/low to cover the HA body."""
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("Open", "High", "Low", "Close"))
    ha_close = (o + h + l + c) / 4
    ha_open = np.empty_like(ha_close)
    if len(ha_open):
        ha_open[0] = (o[0] + c[0]) / 2
    for i in range(1, len(ha_open)):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2
    return pd.DataFrame({
        "HA_Open": ha_open,
        "HA_High": np.maximum.reduce([h, ha_open, ha_close]),
        "HA_Low": np.minimum.reduce([l, ha_open, ha_close]),
        "HA_Close": ha_close,
    }, index=df.index)


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """df: OHLCV indexed by date. Returns a copy with indicator columns added."""
    df = df.copy()
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

    for n in SMA_WINDOWS:
        df[f"SMA_{n}"] = c.rolling(n).mean()
    for n in EMA_SPANS:
        df[f"EMA_{n}"] = c.ewm(span=n, adjust=False).mean()
    df["RSI"] = rsi(c)

    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    df["MACD"] = macd
    df["MACD_signal"] = macd.ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

    prev_close = c.shift(1)
    true_range = pd.concat([h - l, (h - prev_close).abs(), (l - prev_close).abs()], axis=1).max(axis=1)
    df["ATR"] = true_range.ewm(alpha=1 / ATR_WINDOW, adjust=False, min_periods=ATR_WINDOW).mean()
    df["ATR_SMA"] = df["ATR"].rolling(ATR_SIGNAL_WINDOW).mean()

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

    ha = heikin_ashi(df)
    df[list(ha.columns)] = ha

    df["MACD_x"] = cross_events(df["MACD"], df["MACD_signal"])
    df["SMA_x"] = cross_events(df["SMA_10"], df["SMA_50"])
    df["CCI_x"] = cross_events(df["CCI"], pd.Series(0.0, index=df.index))
    df["CMF_x"] = cross_events(df["CMF"], pd.Series(0.0, index=df.index))
    df["Resistance_x"] = cross_events(c, df["Resistance"])
    df["Support_x"] = cross_events(c, df["Support"])
    df["VWAP_x"] = cross_events(c, df["VWAP"])
    df["EMA_x"] = cross_events(df["EMA_9"], df["EMA_18"])
    df["SMA150_x"] = cross_events(c, df["SMA_150"])
    # Heikin Ashi direction change: +1 when the HA candle turns green (HA close
    # above HA open) after a red/doji one, -1 when it turns red/doji after a green one.
    df["HA_x"] = cross_events(df["HA_Close"], df["HA_Open"])
    # Not a directional signal - flags the ATR crossing its own 20-day average,
    # i.e. volatility expanding (+1) or contracting (-1), independent of price direction.
    df["ATR_x"] = cross_events(df["ATR"], df["ATR_SMA"])
    return df


def beta(stock_close: pd.Series, benchmark_close: pd.Series,
        window: int = 252, min_periods: int = 40) -> float:
    """Trailing beta of stock_close vs. benchmark_close from daily returns,
    over the last `window` trading days where both have data (fewer if that's
    all that's available, down to min_periods - below that, NaN).

    Closes are aligned (inner join) *before* computing returns, not after
    independently taking pct_change on each - aligning post-hoc would let a
    gap in one series shift the other's diff across more than one real
    trading day and silently distort the return.
    """
    aligned = pd.concat([stock_close, benchmark_close], axis=1, keys=["stock", "bench"]).dropna()
    returns = aligned.pct_change().dropna().tail(window)
    if len(returns) < min_periods:
        return np.nan
    var = returns["bench"].var()
    if not var or np.isnan(var):
        return np.nan
    return float(returns["stock"].cov(returns["bench"]) / var)


def snapshot(df: pd.DataFrame, lookback: int = 3, benchmark_close: pd.Series | None = None,
             trend_sma: int = 150) -> dict:
    """One row of latest values. Crossovers report the most recent cross
    within the last `lookback` bars (0 = none). `trend_sma` is the user-chosen
    SMA length behind Trend_SMA and the days-above/below counts."""
    x = compute_indicators(df)
    last, close = x.iloc[-1], x["Close"]
    trend = close.rolling(trend_sma).mean()

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
        "SMA_150": float(last["SMA_150"]) if pd.notna(last["SMA_150"]) else np.nan,
        "ATR": float(last["ATR"]) if pd.notna(last["ATR"]) else np.nan,
        "CMF": float(last["CMF"]) if pd.notna(last["CMF"]) else np.nan,
        "Beta": beta(close, benchmark_close) if benchmark_close is not None else np.nan,
        "MACD_x": recent("MACD_x"), "SMA_x": recent("SMA_x"), "CCI_x": recent("CCI_x"),
        "Support_x": recent("Support_x"), "Resistance_x": recent("Resistance_x"),
        "VWAP_x": recent("VWAP_x"), "EMA_x": recent("EMA_x"), "SMA150_x": recent("SMA150_x"),
        "ATR_x": recent("ATR_x"), "CMF_x": recent("CMF_x"), "HA_x": recent("HA_x"),
        "Streak": current_streak(close),
        "Trend_SMA": float(trend.iloc[-1]) if pd.notna(trend.iloc[-1]) else np.nan,
        "Days_Above_SMA": days_above(close, trend),
        "Days_Below_SMA": days_below(close, trend),
    }
