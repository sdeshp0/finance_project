# S&P 500 Signal Dashboard

A Streamlit app that screens S&P 500 stocks for technical signals — RSI,
SMA/MACD/CCI crossovers, streaks, and distance from 52-week highs — with a
sortable table and a per-ticker drill-down chart.

**Not investment advice.** This is an educational/demo project.

## Features

- Pick tickers by GICS sector or paste a custom list
- Indicators: SMA (10/50/100/200), Wilder RSI, MACD, CCI, CMF, 20-day support/resistance
  (Donchian-style channel), and a 20-day rolling VWAP - each with its own crossover/
  breakout signal
- Adjustable RSI thresholds and crossover lookback window
- An overall **Bias** (Bullish/Bearish/Neutral) per ticker, computed as the net of all
  crossover events plus any 2+ day streak - rows are tinted accordingly in the table
- Preset screens (oversold, overbought, bullish/bearish crossover, resistance breakout,
  support breakdown, uptrend pullback, bullish/bearish bias) **plus** a free-text filter
  that narrows the table to rows whose signal summary contains a given word (e.g. "breakout")
- Click any row for a candlestick chart with SMA 50/200, VWAP, support/resistance, RSI,
  and MACD panels
- CSV export of the current view
- Data cached for 1 hour (prices) / 24 hours (S&P 500 constituent list)

## Project structure

```
.
├── app.py                    # Streamlit entrypoint (single page)
├── signals/
│   ├── data.py                # Loads S&P 500 list (Wikipedia) and prices (Yahoo/yfinance)
│   ├── indicators.py          # SMA, Wilder RSI, MACD, CCI, CMF, streaks, crossovers
│   └── summary.py             # Per-ticker snapshot table, signal text, preset screens
├── tests/
│   └── test_indicators.py     # Unit tests for the indicator math
├── requirements.in            # Top-level runtime dependencies
├── requirements.txt           # Pinned, locked dependencies (generated, used for deploy)
├── requirements-dev.in        # Dev-only tools (pytest, ruff)
├── check_env.py                # Standalone script to sanity-check the environment
└── .streamlit/config.toml     # Theme
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
  sorting/highlighting, not a weighted or backtested signal.

## Known limitations / next steps

- No offline fallback yet if Yahoo Finance rate-limits the app (a likely
  issue on shared IPs like Streamlit Community Cloud).
- No footer/disclaimer in the UI itself yet (documented here instead).
- `Ret_1m` uses a 21-trading-day convention rather than a calendar month.
- Large ticker selections (e.g. all 500) take longer on first load, before
  caching kicks in.

## License

For personal/educational use.
