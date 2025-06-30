import pandas as pd


def add_indicators(df):
    df = df.copy()

    df["SMA_10"] = df["Close"].rolling(window=10).mean()
    df["SMA_50"] = df["Close"].rolling(window=50).mean()
    df["SMA_100"] = df["Close"].rolling(window=100).mean()
    df["SMA_200"] = df["Close"].rolling(window=200).mean()

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    df["daily_change"] = df["Close"].pct_change()
    df["Volume_50D_avg"] = df["Volume"].rolling(50).mean()
    df["Volume_Index"] = df["Volume"] / df["Volume_50D_avg"]

    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tp = (high + low + close) / 3
    mean_dev = abs(tp - tp.rolling(20).mean())
    df["CCI"] = (tp - tp.rolling(20).mean()) / (0.015 * mean_dev.rolling(20).mean())

    df["CMF"] = (((2 * close - low - high) / (high - low + 1e-5)) *
                 df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()

    return df

