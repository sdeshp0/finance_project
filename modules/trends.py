def add_consecutive_day_trends(df, max_lookback=5):


    close_prices = df["Close"].copy()

    # Compute daily returns
    daily_returns = close_prices.pct_change().dropna()
    recent_returns = daily_returns[-max_lookback:]

    up_streak = down_streak = 0
    for r in reversed(recent_returns):
        if r > 0:
            if down_streak == 0:
                up_streak += 1
            else:
                break
        elif r < 0:
            if up_streak == 0:
                down_streak += 1
            else:
                break
        else:
            break  # A flat day breaks both streaks

        # Apply streaks to the last row only
        df.loc[df.index[-1], "up_streak"] = up_streak
        df.loc[df.index[-1], "down_streak"] = down_streak

    return df
