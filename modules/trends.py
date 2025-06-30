def add_consecutive_day_trends(df):
    df = df.copy()
    df["up_streak"] = 0
    df["down_streak"] = 0

    for i in range(1, len(df)):
        if df.loc[i, "Close"] > df.loc[i - 1, "Close"]:
            df.loc[i, "up_streak"] = df.loc[i - 1, "up_streak"] + 1
        else:
            df.loc[i, "up_streak"] = 0

        if df.loc[i, "Close"] < df.loc[i - 1, "Close"]:
            df.loc[i, "down_streak"] = df.loc[i - 1, "down_streak"] + 1
        else:
            df.loc[i, "down_streak"] = 0

    for n in range(2, 6):
        df[f"up_{n}_days"] = df["up_streak"] >= (n - 1)
        df[f"down_{n}_days"] = df["down_streak"] >= (n - 1)

    return df