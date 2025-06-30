# 📊 S&P 500 Signal Dashboard

An interactive Streamlit app for exploring technical indicator signals, trend behavior, and market patterns across S&P 500 stocks.

This app fetches real-time price data, computes key technical indicators, identifies crossover signals, and presents a clean, modular dashboard to track stock movement summaries—complete with built-in caching and diagnostic tools.

---

## 🚀 Features

- **Ticker Selection**: Choose stocks via sector filters or custom lists
- **Smart Caching**: Auto-refreshes stale data and caches results efficiently
- **Technical Indicators**: MACD, SMA, CCI, and multi-day trend detection
- **Signal Summarization**: Quick-view signal states for each ticker
- **Dry Run Cache Scanner**: Detects cache freshness before processing
- **Manual + Startup Cache Purging**: Keep storage clean effortlessly
- **Logging System**: Tracks app lifecycle and ticker processing details
- **Configurable Pipeline**: YAML-based settings for cache behavior, logging, retries, and more
- **Streamlit Native UI**: Multi-page layout with in-app controls and developer modes

---

## 🧱 Project Structure
```finance_project/
├── config/
│   └── settings.yaml              # User-defined thresholds (retry delay, etc.)
│
├── logs/
│   └── app.log             # Timestamped app logs
│
├── modules/
│   ├── core_utils/
│   │   ├── path_utils.py          # Project-aware absolute paths
│   │   ├── config_loader.py       # Loads YAML config with fallback
│   │   └── decorators.py          # Streamlit-safe cache wrappers
│   │
│   ├── data_loader.py             # Loads S&P 500 metadata & fetches price data
│   ├── data_pipeline.py           # Processes tickers and generates dashboard data
│   ├── indicators.py              # Computes RSI, MACD, SMA, CCI, etc.
│   ├── crossover_signals.py       # Defines crossover logic (MACD, SMA, CCI)
│   ├── trends.py                  # Tracks consecutive up/down streaks
│   └── signal_summary.py          # Assembles "Signal Summary" strings
│
├── streamlit_app/
│   ├── Home.py                    # App Homepage with ticker selection
│   ├── pages/
│       ├── Dashboard.py           # App page showing the dashboard for selected tickers
├── data/                          # Optional local data storage (e.g. for caching or snapshots)
├── requirements.txt               # Python dependencies
└── README.md                      # Project description and setup

Optional to add later if needed:
tests/                                # Unit tests for core modules
notebooks/                            # For exploratory analysis or indicator prototypes
```

---

## ⚙️ Configuration (`settings.yaml`)

```yaml
max_retries: 2
retry_delay_seconds: 1
max_cache_age_days: 1
purge_on_startup: true
log_level: INFO
log_retention_days: 7
```

---

# Run App Locally

### Install dependencies
pip install -r requirements.txt

### Run the app
streamlit run streamlit_app/Home.py

---

# Notes

- Logs and cache files are stored locally in logs/ and data/
- These are purged automatically on startup if enabled
- No sensitive user data is stored or tracked

📎 Optional Enhancements
- Add backtesting or portfolio analytics
- Enable user-defined indicator thresholds
- Connect to persistent storage (e.g. S3, Firebase)
- Package with Streamlit Desktop for offline desktop distributio

👨‍💻 Developed by
Siddharth N. Deshpande

