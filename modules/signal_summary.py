def generate_signal_summary(row):
    summary = []

    if row.get("MACD_crossover") == 1:
        summary.append("MACD ↑")
    elif row.get("MACD_crossover") == -1:
        summary.append("MACD ↓")

    if row.get("SMA_50_crossover") == 1:
        summary.append("SMA50 ↑")
    elif row.get("SMA_50_crossover") == -1:
        summary.append("SMA50 ↓")

    if row.get("CCI_crossover") == 1:
        summary.append("CCI ↑")
    elif row.get("CCI_crossover") == -1:
        summary.append("CCI ↓")

    if row["up_streak"] > 0:
        summary.append(f"↑ {row['up_streak']}d")
    elif row["down_streak"] > 0:
        summary.append(f"↓ {row['down_streak']}d")

    rsi = row.get("RSI")
    if rsi:
        if rsi > 70:
            summary.append("RSI High")
        elif rsi < 30:
            summary.append("RSI Low")

    return ", ".join(summary) if summary else "–"
