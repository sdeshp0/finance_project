"""Build a static snapshot (constituents + 1y prices) for the app's offline
fallback. Writes to data/snapshot_constituents.csv, data/snapshot_prices.parquet,
and data/snapshot_meta.json.

Run manually:
    python scripts/build_snapshot.py

Run on a schedule via .github/workflows/update_snapshot.yml, which publishes
the files to the repo's `data` branch for the app to download. data/snapshot_*
is gitignored on main.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # allow `import signals` without installing the package

import pandas as pd  # noqa: E402

from signals.data_core import BENCHMARK_TICKER, fetch_prices, fetch_sp500  # noqa: E402
from signals.universes import COUNTRY_ETFS, SECTOR_ETFS  # noqa: E402

DATA_DIR = ROOT / "data"
# Refuse to overwrite the published snapshot with a degraded one: a partly
# rate-limited run can return prices for only some tickers without raising.
MIN_CONSTITUENTS = 480
MIN_PRICE_COVERAGE = 0.95


def main() -> None:
    print("Fetching S&P 500 constituent list from Wikipedia...")
    constituents = fetch_sp500()
    if len(constituents) < MIN_CONSTITUENTS:
        sys.exit(f"Only {len(constituents)} constituents parsed (expected >= {MIN_CONSTITUENTS}); "
                 "keeping the existing snapshot.")
    print(f"  {len(constituents)} constituents fetched.")

    # Include the market benchmark (SPY) and the fixed ETF universes (sector +
    # country) alongside the constituents, so Beta and those sidebar presets
    # still work if Yahoo is unreachable live.
    etf_tickers = set(SECTOR_ETFS) | set(COUNTRY_ETFS)
    tickers = tuple(sorted(set(constituents["Ticker"]) | {BENCHMARK_TICKER} | etf_tickers))
    print(f"Fetching 1y prices for {len(tickers)} tickers - {len(constituents)} S&P 500 "
         f"constituents, the {BENCHMARK_TICKER} benchmark, and {len(etf_tickers)} sector/country "
         "ETFs (this can take a few minutes)...")
    prices = fetch_prices(tickers, period="1y")
    print(f"  {len(prices)}/{len(tickers)} tickers returned data.")
    if len(prices) < MIN_PRICE_COVERAGE * len(tickers):
        sys.exit(f"Price coverage {len(prices)}/{len(tickers)} is below {MIN_PRICE_COVERAGE:.0%}; "
                 "keeping the existing snapshot.")

    # Only write once both fetches have passed their checks, so a failed run
    # leaves all three files untouched.
    DATA_DIR.mkdir(exist_ok=True)
    constituents.to_csv(DATA_DIR / "snapshot_constituents.csv", index=False)
    # dict[ticker -> OHLCV frame] -> one wide frame with MultiIndex columns (ticker, field)
    wide = pd.concat(prices, axis=1)
    wide.to_parquet(DATA_DIR / "snapshot_prices.parquet")

    meta = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "last_bar": f"{wide.index.max():%Y-%m-%d}",
        "tickers": len(prices),
    }
    (DATA_DIR / "snapshot_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Snapshot written. as_of={meta['as_of']}, last_bar={meta['last_bar']}, "
          f"tickers={meta['tickers']}")


if __name__ == "__main__":
    main()
