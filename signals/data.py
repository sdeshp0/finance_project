"""Streamlit-facing data loading: live fetch (cached) with a snapshot fallback
for when Yahoo Finance or Wikipedia are unreachable - e.g. rate-limited on a
shared IP like Streamlit Community Cloud. The snapshot files under data/ are
produced by scripts/build_snapshot.py, normally on a schedule (see
.github/workflows/update_snapshot.yml).
"""
import json
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from signals.data_core import BENCHMARK_TICKER, fetch_prices, fetch_sp500

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SNAPSHOT_CONSTITUENTS = DATA_DIR / "snapshot_constituents.csv"
SNAPSHOT_PRICES = DATA_DIR / "snapshot_prices.parquet"
SNAPSHOT_META = DATA_DIR / "snapshot_meta.json"

# Plain cached versions of the live fetchers (no fallback) - used directly by
# the safe wrappers below, and available on their own if ever needed.
load_sp500 = st.cache_data(ttl=24 * 3600, show_spinner=False)(fetch_sp500)
load_prices = st.cache_data(ttl=3600, show_spinner=False)(fetch_prices)


def snapshot_asof() -> str | None:
    if not SNAPSHOT_META.exists():
        return None
    try:
        return json.loads(SNAPSHOT_META.read_text()).get("as_of")
    except Exception:
        return None


def _read_snapshot_constituents() -> pd.DataFrame:
    return pd.read_csv(SNAPSHOT_CONSTITUENTS)


def _read_snapshot_prices(tickers: tuple[str, ...]) -> dict[str, pd.DataFrame]:
    wide = pd.read_parquet(SNAPSHOT_PRICES)  # MultiIndex columns: (ticker, field)
    have = {t for t, _ in wide.columns} & set(tickers)
    return {t: wide[t].dropna(how="all") for t in have}


@st.cache_data(ttl=3600, show_spinner=False)
def load_benchmark_close(period: str = "1y") -> tuple[pd.Series | None, str, str | None]:
    """The market benchmark's Close series, for beta. Reuses load_prices_safe
    (and therefore its live/snapshot fallback) for a single ticker."""
    try:
        prices, source, asof = load_prices_safe((BENCHMARK_TICKER,), period)
    except Exception as e:
        log.warning("Benchmark (%s) unavailable (%s); Beta will be blank.", BENCHMARK_TICKER, e)
        return None, "unavailable", None
    df = prices.get(BENCHMARK_TICKER)
    if df is None:
        return None, "unavailable", None
    return df["Close"], source, asof


@st.cache_data(ttl=3600, show_spinner=False)
def load_sp500_safe() -> tuple[pd.DataFrame, str, str | None]:
    """Returns (constituents, source, as_of). source is 'live' or 'snapshot'."""
    try:
        return load_sp500(), "live", None
    except Exception as e:
        log.warning("Live S&P 500 list failed (%s); trying snapshot.", e)
        if not SNAPSHOT_CONSTITUENTS.exists():
            raise
        return _read_snapshot_constituents(), "snapshot", snapshot_asof()


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices_safe(tickers: tuple[str, ...], period: str = "1y"):
    """Returns (prices, source, as_of). source is 'live' or 'snapshot'."""
    try:
        return load_prices(tickers, period), "live", None
    except Exception as e:
        log.warning("Live price download failed (%s); trying snapshot.", e)
        if not SNAPSHOT_PRICES.exists():
            raise
        prices = _read_snapshot_prices(tickers)
        if not prices:
            raise RuntimeError("No matching tickers found in the snapshot either.") from e
        return prices, "snapshot", snapshot_asof()
