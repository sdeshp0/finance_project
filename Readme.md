# S&P 500 Signal Dashboard

A Streamlit app that screens S&P 500 stocks for technical signals — RSI,
SMA/MACD/CCI crossovers, streaks, and distance from 52-week highs — with a
sortable table and a per-ticker drill-down chart.

**Not investment advice.** This is an educational/demo project.

## Features

- Pick tickers by GICS sector or paste a custom list
- **Configurable history length** for the live fetch (6 months to max available) -
  longer history gives indicators like SMA 200 a fuller warm-up, at the cost of a
  slower first load
- Indicators: SMA (10/50/100/150/200), EMA (9/18), Wilder RSI, MACD, ATR, CCI, CMF,
  20-day support/resistance (Donchian-style channel), and a 20-day rolling VWAP -
  the crossover-based ones (SMA, MACD, CCI, VWAP, support, resistance) each have
  their own crossover/breakout signal in the table
- Adjustable RSI thresholds and crossover lookback window
- An overall **Bias** (Bullish/Bearish/Neutral) per ticker, computed as the net of all
  crossover events plus any 2+ day streak - rows are tinted accordingly in the table
- Preset screens (oversold, overbought, bullish/bearish crossover, resistance breakout,
  support breakdown, uptrend pullback, bullish/bearish bias) **plus** a free-text filter
  that narrows the table to rows whose signal summary contains a given word (e.g. "breakout")
- Click any row for a **configurable candlestick chart** - pick which overlay lines
  (any SMA/EMA, VWAP, support, resistance) and which lower panels (RSI, MACD, ATR)
  to show; the current default set is a sensible starting point, not the only option
- **CSV export** of either the current screener table, or the complete indicator
  history for a single selected ticker (every column, every date) - the same data
  driving its chart
- Data cached for 1 hour (prices) / 24 hours (S&P 500 constituent list)

## Project structure

```
.
├── app.py                          # Streamlit entrypoint (single page)
├── signals/
│   ├── data_core.py                 # Pure fetch functions (no Streamlit) - Wikipedia + yfinance
│   ├── data.py                      # Streamlit-cached wrappers + live/snapshot fallback
│   ├── indicators.py                # SMA, Wilder RSI, MACD, CCI, CMF, support/resistance, VWAP
│   └── summary.py                   # Per-ticker table, signal text, Bias, preset screens
├── scripts/
│   └── build_snapshot.py            # Builds the offline fallback snapshot (run manually or by CI)
├── .github/workflows/
│   └── update_snapshot.yml          # Scheduled job that refreshes the snapshot and commits it
├── data/
│   ├── snapshot_constituents.csv    # Fallback S&P 500 list (generated)
│   ├── snapshot_prices.parquet      # Fallback 1y prices (generated)
│   └── snapshot_meta.json           # Snapshot timestamp (generated)
├── tests/
│   └── test_indicators.py           # Unit tests for the indicator math
├── requirements.in                  # Top-level runtime dependencies (unpinned source)
├── requirements.txt                 # Pinned dependencies - used for local installs and deploy
├── requirements-dev.in              # Dev-only tools (pytest, ruff)
├── check_env.py                      # Standalone script to sanity-check the environment
└── .streamlit/config.toml           # Theme
```

## Setup

Requires Python 3.12. This project uses [uv](https://docs.astral.sh/uv/) for
environment and dependency management.

```bash
uv venv --python 3.12
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1

uv pip install -r requirements.txt -r requirements-dev.in
```

If you're not using uv, plain `pip install -r requirements.txt -r requirements-dev.in`
in a `venv` works the same way.

### Verify the environment

```bash
python check_env.py
```

Checks that the Wikipedia constituent scrape and a batched Yahoo Finance
download both work before you run the app — useful after any dependency
upgrade, since this project previously broke silently when yfinance/pandas
changed their return shapes.

## Running

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually http://localhost:8501). Choose
sectors or paste tickers in the sidebar, adjust RSI/lookback if you like,
and click any row in the table to see its chart.

## Testing

```bash
pytest -q
```

Covers the indicator math directly (RSI bounds, crossover detection, streak
counting, SMA/MACD correctness) without needing network access or Streamlit.

## Data sources

- **Constituents:** scraped from the [Wikipedia S&P 500 list](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies).
  Tickers with dots (e.g. `BRK.B`) are normalized to Yahoo's dash format (`BRK-B`).
- **Prices:** [Yahoo Finance](https://finance.yahoo.com/) via `yfinance`, downloaded
  in batches of 100 tickers to avoid one request per symbol.

Both sources can rate-limit or go down, in which case the app currently
displays an error banner. A cached-snapshot fallback for deployment is a
planned improvement (see below).

## Indicator notes

- **Support / Resistance**: the 20-day high/low of the *prior* bars (today's own bar is
  excluded), so a close above resistance or below support is a genuine breakout/breakdown,
  not just an artifact of today being a new high or low.
- **VWAP**: true VWAP resets every trading day and needs intraday (tick or minute) data,
  which this project doesn't have. What's shown is a **rolling 20-day volume-weighted
  average price** using daily bars - a common approximation, but not the same number
  you'd see on an intraday VWAP chart. Treat it as a volume-aware moving average.
- **Bias**: a simple net count of crossover events (MACD, SMA 10/50, CCI, VWAP, support,
  resistance) plus the current streak if it's 2+ days. It's a quick-glance label for
  sorting/highlighting, not a weighted or backtested signal. ATR, SMA 150, and EMA 9/18
  are available on the chart and in the per-ticker CSV, but aren't part of this scoring -
  they're chart/analysis tools rather than screener signals for now.
- **ATR (Average True Range)**: Wilder-smoothed, 14-day window - a volatility measure,
  not a directional one, so it has no crossover event.

## Offline fallback

Yahoo Finance and Wikipedia can both throttle or block shared IPs, which
Streamlit Community Cloud uses - a live demo that errors out on a bad day
makes a poor impression. To guard against that, the app falls back to a
committed snapshot when a live fetch fails entirely:

- `signals/data_core.py` holds the plain fetch functions (no Streamlit
  dependency), so the same code path is used by the app and by the snapshot
  script.
- `scripts/build_snapshot.py` fetches the current constituent list and one
  year of prices, and writes them to `data/snapshot_constituents.csv`,
  `data/snapshot_prices.parquet`, and `data/snapshot_meta.json`.
- `signals/data.py` exposes `load_sp500_safe()` / `load_prices_safe()`, which
  try the live source first and fall back to reading those snapshot files if
  the live call raises. Either way they return `(data, source, as_of)`, and
  the app shows a visible banner when `source == "snapshot"`.
- `.github/workflows/update_snapshot.yml` runs the script on a schedule
  (weekdays, 22:00 UTC - after the US market close year-round) and commits
  the refreshed files back to the repo. It can also be triggered manually
  from the **Actions** tab (`workflow_dispatch`).

**Before your first deploy**, generate an initial snapshot so the fallback
has something to use from day one - either run it locally and commit the
output:

```bash
python scripts/build_snapshot.py
git add data/snapshot_* && git commit -m "Add initial data snapshot"
```

or push the repo first, then trigger the workflow once manually from the
Actions tab.

## Deploying to Streamlit Community Cloud

1. Push the repo to GitHub, including `requirements.txt` and the `data/`
   snapshot files from the step above.
2. Go to [share.streamlit.io](https://share.streamlit.io), click **New app**,
   and pick this repo/branch with `app.py` as the main file.
3. Under **Advanced settings**, set the Python version to match what you
   tested locally (3.12; use 3.11 if 3.12 isn't offered).
4. Deploy. Community Cloud installs from `requirements.txt` automatically.
5. Keep an eye on the first cold load - it reinstalls dependencies and starts
   fresh each time the app wakes from sleeping, and Yahoo is more likely to
   throttle a shared cloud IP than your own machine. That's exactly what the
   snapshot fallback above is for.
6. There are no secrets to configure yet. If you add an API key later (e.g.
   an alternative data provider), put it in the app's **Secrets** panel and
   read it via `st.secrets`, and never commit it.

The filesystem on Community Cloud is ephemeral - nothing the app writes at
runtime persists, which is why the snapshot has to be committed to the repo
rather than generated on the fly by the app itself.

## Known limitations / next steps

- No footer/disclaimer in the UI itself yet (documented here instead).
- `Ret_1m` uses a 21-trading-day convention rather than a calendar month.
- Large ticker selections, or a long history length (5y/10y/max), take longer on
  first load, before caching kicks in.
- The snapshot fallback is all-or-nothing per request: if the live fetch
  returns data for *some* tickers it's used as-is (those tickers just show
  up in the "no data" expander); the snapshot only kicks in when the live
  fetch fails completely. The snapshot itself is always ~1 year of history,
  regardless of the History length setting - a longer lookback only applies
  when live data is actually available.

## License

For personal/educational use.
