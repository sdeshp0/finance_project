# S&P 500 Signal Dashboard

A Streamlit app that screens S&P 500 stocks for technical signals — RSI,
SMA/MACD/CCI crossovers, streaks, and distance from 52-week highs — with a
sortable table and a per-ticker drill-down chart.

**Not investment advice.** This is an educational/demo project.

## Features

- Four ways to pick tickers: S&P 500 by GICS sector, the 11 US Sector SPDR ETFs,
  a curated set of 16 major single-country ETFs, or a custom comma-separated list
- **Configurable history length** for the live fetch (6 months to max available) -
  longer history gives indicators like SMA 200 a fuller warm-up, at the cost of a
  slower first load
- Indicators: SMA (10/50/100/150/200), EMA (9/18), Wilder RSI, MACD, ATR, CCI, CMF,
  20-day support/resistance (Donchian-style channel), and a 20-day rolling VWAP - every
  one of them except RSI and ATR has its own crossover/breakout signal (ATR gets
  a separate "volatility expanding/contracting" signal instead, since it's not directional)
- Adjustable RSI thresholds and crossover lookback window
- **Days above SMA150**: how many trading days in a row each ticker has closed above
  its 150-day SMA. A sidebar setting ("Min days above SMA150", default 20) highlights
  tickers at or past that count and drives an "Above SMA150 for X+ days" screen
- An overall **Bias** (Bullish/Bearish/Neutral) per ticker, computed as the net of all
  crossover events plus any 2+ day streak - rows are tinted accordingly in the table
- Preset screens, grouped into categories (Overall, RSI, Trend crossovers, Price
  levels, Volatility, Combo screens) in a two-level dropdown so the list stays easy
  to scan as more screens get added, **plus** a free-text filter that narrows the table to rows whose signal summary contains a given word (e.g. "breakout")
- Click any row for a **configurable candlestick chart** - pick which overlay lines
  (any SMA/EMA, VWAP, support, resistance) and which lower panels (RSI, MACD, ATR,
  CMF, CCI) to show; the current default set is a sensible starting point, not the
  only option
- **Beta** vs. SPY (the market benchmark) - trailing, from daily returns over
  up to the last 252 trading days, shown as a column in the screener table -
  plus **Beta vs Sector**, comparing it to a leave-one-out average of its
  sector peers currently loaded in the table (only meaningful with the S&P
  500 sector picker and at least 3 other sector peers loaded)
- **CSV export** of either the current screener table, or the complete indicator
  history for a single selected ticker (every column, every date) - the same data
  driving its chart
- **Backtesting** for the selected ticker - pick any crossover signal, the RSI
  mean-reversion rule, or the overall Bias score, choose direction (long/short/both),
  an exit rule (fixed holding period or until the opposite signal fires, with the
  holding period doubling as a safety cap either way), and an optional stop-loss and
  trading cost, then see the trade log, summary stats, and an equity curve vs.
  buy-and-hold
- Data cached for 1 hour (prices) / 24 hours (S&P 500 constituent list)

## Project structure

```
.
├── app.py                          # Streamlit entrypoint (single page)
├── signals/
│   ├── data_core.py                 # Pure fetch functions (no Streamlit) - Wikipedia + yfinance
│   ├── data.py                      # Streamlit-cached wrappers + live/snapshot fallback
│   ├── indicators.py                # SMA, Wilder RSI, MACD, CCI, CMF, support/resistance, VWAP
│   ├── summary.py                   # Per-ticker table, signal text, Bias, preset screens
│   ├── backtest.py                  # Event-based backtest engine (signal -> trade log -> stats)
│   └── universes.py                 # Fixed ETF ticker lists (US sectors, countries)
├── scripts/
│   └── build_snapshot.py            # Builds the offline fallback snapshot (run manually or by CI)
├── .github/workflows/
│   └── update_snapshot.yml          # Scheduled job that refreshes the snapshot and commits it
├── data/
│   ├── snapshot_constituents.csv    # Fallback S&P 500 list (generated)
│   ├── snapshot_prices.parquet      # Fallback 1y prices (generated)
│   └── snapshot_meta.json           # Snapshot timestamp (generated)
├── tests/
│   ├── test_indicators.py           # Unit tests for the indicator math
│   └── test_backtest.py             # Unit tests for the backtest engine
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
- **Bias**: a simple net count of directional crossover events (MACD, SMA 10/50, CCI,
  VWAP, support, resistance, EMA 9/18, price vs SMA 150) plus the current streak if it's
  2+ days. It's a quick-glance label for sorting/highlighting, not a weighted or
  backtested signal.
- **Days above SMA150**: consecutive closes above the 150-day SMA, counted back from
  the latest bar - 0 if today's close is at or below it, blank until the SMA has its
  150 days of warm-up. Because the count starts only once the SMA exists, it's capped
  by the history loaded (about 100 days with the default 1 year); pick a longer
  History length for larger thresholds. It's a sustained state rather than a fresh
  event, so it's highlighted and screenable but *not* added to Bias (the SMA150
  crossover already counts there).
- **CMF (Chaikin Money Flow)**: 20-day, from the money-flow multiplier
  (`((Close-Low)-(High-Close))/(High-Low)`) weighted by volume - positive means
  the close is sitting toward the top of its daily range on heavier volume
  (buying pressure/accumulation), negative means the bottom (selling
  pressure/distribution). Its signal is a zero-cross, the same treatment CCI
  already gets, and it's directional, so it's included in Bias.
- **ATR (Average True Range)**: Wilder-smoothed, 14-day window - a volatility
  *magnitude*, not a direction, so it doesn't factor into Bias. Instead it gets its own
  signal: ATR crossing its own 20-day average, flagged as "volatility expanding" or
  "contracting." That can accompany a move in either direction, which is exactly why
  it's kept separate from the bullish/bearish scoring.
- **Beta**: the slope of the stock's daily returns regressed against SPY's daily
  returns (`Cov(stock, SPY) / Var(SPY)`), using the closes aligned first and returns
  computed *after* aligning (not the other way around, which could silently distort
  a return across a data gap). Uses up to the trailing 252 trading days, or however
  many overlapping days are available if less history is loaded; blank if there
  are fewer than 40 overlapping days to estimate from. SPY is fetched the same way
  as every other ticker, including the live/snapshot fallback - `build_snapshot.py`
  includes SPY in the snapshot for exactly that reason. Beta is a *market-relative*
  risk measure only - it says nothing about a stock's own idiosyncratic volatility
  (that's closer to what ATR captures), and it isn't wired into Bias or backtesting
  at this point. A **sector-adjusted** variant is now implemented as **Beta vs
  Sector**: each ticker's Beta divided by a *leave-one-out* average of its
  sector peers' Beta (excluding its own value, so a ticker can't dominate its
  own comparison group in a small sample). This only uses sector peers
  currently loaded in the table - not the full 500 - and needs at least 3
  other peers with a valid Beta in that sector before showing a value;
  otherwise it's blank. It's also unavailable with a custom (non-sector)
  ticker list, since there's no sector to compare against. Of the sector-
  adjustment approaches discussed (beta vs. a sector index instead of SPY,
  peer-relative beta, or Vasicek-style shrinkage toward the sector mean),
  this is the peer-relative version - the other two remain unimplemented.

## Backtesting

For the ticker selected in the drill-down chart, an expander below it lets you
simulate trades off any signal already computed for that ticker:

- **Signal**: any crossover column (MACD, SMA 10/50, CCI, VWAP, support,
  resistance, EMA 9/18, SMA150), RSI mean-reversion (oversold -> long,
  overbought -> short, using the same thresholds set in the sidebar), or the
  overall Bias score (a trade opens the day Bias *changes into* Bullish or
  Bearish, not on every day it stays there).
- **Entries** always execute at the **next bar's open** after the signal fired
  at the prior bar's close - using that bar's own close would be look-ahead
  bias (you can't act on information before it exists).
- **Exit**: fixed holding period, or "until the opposite signal fires" - and
  in that second mode, the holding period still applies as a maximum cap, so
  a trade can't run forever if the signal simply never reverses.
- **Stop-loss** (optional) is checked every bar and can end a trade early
  under either exit rule.
- **Direction**: long-only, short-only, or both (a bullish event opens a
  long, a bearish event opens a short). Only one position is held at a time -
  a new signal while already in a trade is ignored until that trade closes.
- Output: a trade log (downloadable as CSV), summary stats (win rate, average
  return, max drawdown, total compounded return), and an equity curve
  compared against simply buying and holding over the same period.

**Read this before trusting a result.** This is a single-ticker historical
simulation with everything that implies:
- Trade counts are often small (a handful to a few dozen over a year), which
  isn't a statistically reliable sample - the win rate and average return
  swing a lot with just one or two trades.
- The RSI thresholds and crossover lookback are the same ones you can freely
  drag around elsewhere in the sidebar. Tuning them until a backtest looks
  good is a textbook way to overfit to noise rather than find something real.
- No slippage is modeled beyond the optional flat basis-point cost you set
  yourself; a market order in practice may fill worse than the bar's open.
- The equity curve compounds trade-by-trade (it only steps on exit dates),
  while buy-and-hold is continuously invested every calendar day - the two
  are plotted together for a visual sense of scale, not as directly
  comparable time series.
- None of this is investment advice, and past performance in a backtest is
  not a guarantee of anything going forward.

## Offline fallback

Yahoo Finance and Wikipedia can both throttle or block shared IPs, which
Streamlit Community Cloud uses - a live demo that errors out on a bad day
makes a poor impression. To guard against that, the app falls back to a
committed snapshot when a live fetch fails entirely:

- `signals/data_core.py` holds the plain fetch functions (no Streamlit
  dependency), so the same code path is used by the app and by the snapshot
  script.
- `scripts/build_snapshot.py` fetches the current constituent list, one year of
  prices for every constituent **plus the SPY benchmark and the fixed US Sector /
  Country ETF universes** from `signals/universes.py`, and writes them to
  `data/snapshot_constituents.csv`, `data/snapshot_prices.parquet`, and
  `data/snapshot_meta.json`. The ETF universes aren't scraped from anywhere -
  they're the same hardcoded lists the sidebar presets use - so only their
  *prices* need a fallback, not a constituent list.
- `signals/data.py` exposes `load_sp500_safe()` / `load_prices_safe()` /
  `load_benchmark_close()`, which try the live source first and fall back to
  reading those snapshot files if the live call raises. Either way they return
  `(data, source, as_of)`, and
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

**If you already have a snapshot deployed from before the ETF presets were
added**, it won't have the sector/country ETF tickers in it yet (or SPY, if
it predates Beta). Re-run `python scripts/build_snapshot.py` (or trigger the
Action manually once) and commit the refresh - until then, the offline
fallback simply won't have those tickers to serve, the same as if Yahoo were
down for any other ticker not yet in the snapshot.

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
- **The offline snapshot covers S&P 500 constituents, SPY, and the US
  Sector/Country ETF universes** - any *custom* ticker list still has no
  offline fallback, since there's no way to know in advance which tickers
  someone might type in. If Yahoo is unreachable, a custom list shows the
  same "data load failed" error as before; the three preset-based modes now
  fall back gracefully.
- "Beta vs Sector" doesn't apply to the ETF universes (each ETF has no GICS
  sector of its own in this app) or custom lists - it's blank there by
  design, not a bug.

## License

For personal/educational use.
