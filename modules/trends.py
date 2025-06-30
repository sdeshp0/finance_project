def add_consecutive_day_trends(df, lookback=5):
    if df.empty or "Close" not in df.columns:
        df["up_streak"] = 0
        df["down_streak"] = 0
        return df

    recent = df["Close"].dropna()[-(lookback + 1):]

    if len(recent) < lookback + 1:
        df.loc[df.index[-1], "up_streak"] = 0
        df.loc[df.index[-1], "down_streak"] = 0
        return df

    diffs = recent.diff().dropna()
    if all(d > 0 for d in diffs):
        df.loc[df.index[-1], "up_streak"] = len(diffs)
        df.loc[df.index[-1], "down_streak"] = 0
    elif all(d < 0 for d in diffs):
        df.loc[df.index[-1], "down_streak"] = len(diffs)
        df.loc[df.index[-1], "up_streak"] = 0
    else:
        df.loc[df.index[-1], "up_streak"] = 0
        df.loc[df.index[-1], "down_streak"] = 0

    return df

