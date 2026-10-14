"""Pure data-fetching functions with no Streamlit dependency, so the same code
runs inside the app (wrapped with st.cache_data in data.py) and standalone in
the snapshot-building script/GitHub Action."""
import logging
from datetime import date, datetime, time, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

log = logging.getLogger(__name__)

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {"User-Agent": "Mozilla/5.0 (sp500-signal-dashboard demo)"}
FIELDS = ["Open", "High", "Low", "Close", "Volume"]
CHUNK = 100  # tickers per Yahoo request
MIN_BARS = 30
BENCHMARK_TICKER = "SPY"  # market benchmark used for Beta

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)
# History lengths the (1-year) snapshot can serve, and how far back each reaches
# from the snapshot's last bar. Anything longer always needs a live fetch.
SNAPSHOT_PERIODS = {"6mo": pd.DateOffset(months=6), "1y": pd.DateOffset(years=1)}


def fetch_sp500() -> pd.DataFrame:
    r = requests.get(WIKI_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    df = pd.read_html(StringIO(r.text))[0]
    df["Ticker"] = df["Symbol"].str.replace(".", "-", regex=False)  # BRK.B -> BRK-B
    return df[["Ticker", "Security", "GICS Sector", "GICS Sub-Industry"]]


def fetch_prices(tickers: tuple[str, ...], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Batched download -> {ticker: OHLCV frame}. Raises if nothing came back."""
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


def last_trading_day(now: datetime) -> date:
    """The most recent weekday whose regular session has closed as of `now`
    (tz-aware). Exchange holidays are ignored: on one, this asks for a bar that
    doesn't exist, so the snapshot looks stale and the app does a live fetch -
    an unnecessary download, but never a wrong answer."""
    local = now.astimezone(MARKET_TZ)
    d = local.date()
    if local.time() < MARKET_CLOSE:
        d -= timedelta(days=1)
    while d.weekday() >= 5:  # Sat/Sun
        d -= timedelta(days=1)
    return d


def snapshot_is_fresh(last_bar: date, now: datetime) -> bool:
    return last_bar >= last_trading_day(now)


def slice_snapshot(wide: pd.DataFrame, tickers: tuple[str, ...],
                   period: str) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Cut the wide snapshot frame (MultiIndex columns: ticker, field) down to
    `tickers` and `period`. Returns ({ticker: OHLCV frame}, tickers not in the
    snapshot). `period` must be a key of SNAPSHOT_PERIODS."""
    start = wide.index.max() - SNAPSHOT_PERIODS[period]
    wide = wide[wide.index > start]
    have = set(wide.columns.get_level_values(0))
    out, missing = {}, []
    for t in tickers:
        df = wide[t].dropna(subset=["Close"]) if t in have else None
        if df is not None and len(df) >= MIN_BARS:
            out[t] = df
        else:
            missing.append(t)
    return out, missing
