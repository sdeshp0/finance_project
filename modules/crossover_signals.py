def add_macd_crossover(df):
    df = df.copy()
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    df["MACD_12_26_9"] = macd
    df["MACDs_12_26_9"] = signal
    df["MACDh_12_26_9"] = macd - signal
    df["MACD_crossover"] = (macd > signal).astype(int).diff().fillna(0).astype(int)
    return df

def add_sma_crossover(df):
    df = df.copy()
    df["SMA_50_crossover"] = (df["SMA_10"] > df["SMA_50"]).astype(int).diff().fillna(0).astype(int)
    return df

def add_cci_crossover(df):
    df = df.copy()
    df["CCI_crossover"] = (df["CCI"] > 0).astype(int).diff().fillna(0).astype(int)
    return df