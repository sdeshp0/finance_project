"""Data loading: S&P 500 constituents (Wikipedia) and prices (Yahoo via yfinance)."""
import logging
from io import StringIO

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

log = logging.getLogger(__name__)

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {"User-Agent": "Mozilla/5.0 (sp500-signal-dashboard demo)"}
FIELDS = ["Open", "High", "Low", "Close", "Volume"]
CHUNK = 100  # tickers per Yahoo request
MIN_BARS = 30


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_sp500() -> pd.DataFrame:
    r = requests.get(WIKI_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    df = pd.read_html(StringIO(r.text))[0]
    df["Ticker"] = df["Symbol"].str.replace(".", "-", regex=False)  # BRK.B -> BRK-B
    return df[["Ticker", "Security", "GICS Sector", "GICS Sub-Industry"]]


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(tickers: tuple[str, ...], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Batched download -> {ticker: OHLCV frame}. Raises if nothing came back,
    so a failed fetch is never cached."""
    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(tickers), CHUNK):
        chunk = list(tickers[i:i + CHUNK])
        try:
            raw = yf.download(chunk, period=period, interval="1d", group_by="ticker",
                              auto_adjust=True, threads=True, progress=False)
        except Exception as e:
            log.warning("yfinance chunk failed (%s...): %s", chunk[0], e)
            continue
        if raw.empty:
            continue
        present = set(raw.columns.get_level_values(0))
        for t in chunk:
            if t in present:
                df = raw[t].dropna(subset=["Close"])
                if len(df) >= MIN_BARS:
                    out[t] = df[FIELDS].copy()
    if not out:
        raise RuntimeError("No price data returned (Yahoo may be rate-limiting or offline).")
    return out
