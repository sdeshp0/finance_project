"""Environment smoke test. Run: python check_env.py

Checks the two things most likely to break this project:
  1. Scraping the S&P 500 table from Wikipedia
  2. Batched price download from Yahoo via yfinance
"""
import sys
from importlib.metadata import version
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
UA = {"User-Agent": "Mozilla/5.0 (finance-project env check)"}


def ok(msg):
    print(f"  [ OK ] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


print(f"Python {sys.version.split()[0]}")
for pkg in ["streamlit", "pandas", "numpy", "yfinance", "requests", "lxml", "plotly", "pyarrow"]:
    try:
        print(f"  {pkg:<10} {version(pkg)}")
    except Exception:
        fail(f"{pkg} not installed")

print("\n1. Wikipedia S&P 500 table")
try:
    r = requests.get(WIKI_URL, headers=UA, timeout=15)
    r.raise_for_status()
    table = pd.read_html(StringIO(r.text))[0]
    table["Ticker"] = table["Symbol"].str.replace(".", "-", regex=False)
    ok(f"{len(table)} constituents; columns include {list(table.columns[:4])}")
    ok(f"BRK-B present after normalizing: {'BRK-B' in set(table['Ticker'])}")
except Exception as e:
    fail(f"{type(e).__name__}: {e}")

print("\n2. yfinance batch download")
try:
    tickers = ["AAPL", "MSFT", "BRK-B"]
    raw = yf.download(tickers, period="1y", interval="1d",
                      group_by="ticker", auto_adjust=True,
                      threads=True, progress=False)
    if raw.empty:
        fail("Empty result (rate-limited or offline?)")
    else:
        ok(f"shape={raw.shape}, index type={type(raw.index).__name__}")
        ok(f"column levels: {raw.columns.nlevels}, "
           f"tickers={sorted(set(raw.columns.get_level_values(0)))}")
        aapl = raw["AAPL"].dropna(how="all")
        ok(f"AAPL fields={list(aapl.columns)}, last date={aapl.index[-1].date()}")

    print("\n   Single-ticker shape (matters for old code assumptions):")
    one = yf.download("AAPL", period="1mo", group_by="ticker",
                      auto_adjust=True, progress=False)
    ok(f"columns nlevels={one.columns.nlevels}: {list(one.columns)[:3]}")
except Exception as e:
    fail(f"{type(e).__name__}: {e}")
