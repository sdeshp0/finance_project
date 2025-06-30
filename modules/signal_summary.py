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

    for n in [5, 4, 3, 2]:
        if row.get(f"up_{n}_days"):
            summary.append(f"Up {n}d")
            break
        elif row.get(f"down_{n}_days"):
            summary.append(f"Down {n}d")
            break

    rsi = row.get("RSI")
    if rsi:
        if rsi > 70:
            summary.append("RSI High")
        elif rsi < 30:
            summary.append("RSI Low")

    return ", ".join(summary) if summary else "–"
