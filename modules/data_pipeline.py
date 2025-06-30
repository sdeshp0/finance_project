import os
import pandas as pd
import time
from datetime import datetime, timedelta

from modules.data_loader import fetch_price_data
from modules.indicators import add_indicators
from modules.crossover_signals import add_macd_crossover, add_sma_crossover, add_cci_crossover
from modules.trends import add_consecutive_day_trends
from modules.signal_summary import generate_signal_summary

from modules.core_utils.config_loader import load_config
from modules.core_utils.path_utils import DATA_DIR, LOGS_DIR

import logging

config = load_config()
MAX_RETRIES = config.get("max_retries", 2)
RETRY_DELAY = config.get("retry_delay_seconds", 1)
MAX_CACHE_AGE_DAYS = config.get("max_cache_age_days", 1)


def initialize_logging():
    log_retention_days = config.get("log_retention_days", 3)
    log_level = config.get("log_level", "INFO").upper()
    log_path = os.path.join(LOGS_DIR, "app.log")

    os.makedirs(LOGS_DIR, exist_ok=True)

    # Auto-purge if log file is too old
    if os.path.exists(log_path):
        last_modified = datetime.fromtimestamp(os.path.getmtime(log_path))
        if (datetime.now() - last_modified) > timedelta(days=log_retention_days):
            os.remove(log_path)

    logging.basicConfig(
        filename=log_path,
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M"
    )

def cache_path_for(ticker):
    return os.path.join(DATA_DIR, f"{ticker}.pkl")


def is_cache_fresh(df, max_age_days):
    if df is None or df.empty or "Date" not in df.columns:
        return False
    try:
        cache_date = pd.to_datetime(df["Date"].iloc[0]).date()
        return (datetime.today().date() - cache_date) <= timedelta(days=max_age_days)
    except Exception:
        return False


def process_ticker(ticker):
    os.makedirs(DATA_DIR, exist_ok=True)
    cache_path = cache_path_for(ticker)
    cached_df = pd.read_pickle(cache_path) if os.path.exists(cache_path) else None
    if is_cache_fresh(cached_df, MAX_CACHE_AGE_DAYS):
        logging.info(f"📦 Cache HIT for {ticker} — loaded from {cache_path}")
        return cached_df
    else:
        logging.info(f"📦 Cache MISS for {ticker}")

    df = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            df = fetch_price_data(ticker)
            if df.empty:
                raise ValueError("Empty DataFrame")
            break
        except Exception as e:
            print(f"[Retry {attempt}/{MAX_RETRIES}] Download failed for {ticker}: {e}")
            logging.exception(f"[Retry {attempt}/{MAX_RETRIES}] Download failed for {ticker}: {e}")
            time.sleep(RETRY_DELAY)
    else:
        print(f"[ERROR] Failed to fetch data for {ticker} after {MAX_RETRIES + 1} attempts.")
        return None

    try:
        dates = df['Date']
        df = df[ticker]
        df['Date'] = dates
        df['Ticker'] = ticker

        df = add_indicators(df)
        logging.debug(f"🧮 Added indicators to {ticker}, shape: {df.shape}")

        df = add_macd_crossover(df)
        logging.debug(f"📐 MACD crossovers computed")

        df = add_sma_crossover(df)
        df = add_cci_crossover(df)
        logging.debug(f"📈 SMA/CCI crossovers done")

        df = add_consecutive_day_trends(df)
        logging.debug(f"📈 Consecutive day trends calculated")

        latest = df.iloc[-1:].copy()
        latest["Ticker"] = ticker
        latest["Signal Summary"] = latest.apply(generate_signal_summary, axis=1)
        logging.debug(f"🧮 Added Signal summary to {ticker}")

        latest["Date"] = pd.to_datetime(df["Date"].iloc[-1])  # Explicitly preserve the final date
        latest.to_pickle(cache_path)  # Save to cache
        return latest
    except Exception as e:
        print(f"[ERROR] Processing failed for {ticker}: {e}")
        logging.exception(f"🔥 ERROR processing {ticker}: {e}")
        return None


def generate_dashboard_data(ticker_list):
    results = []
    failures = []

    logging.info(f"🧺 Processing {len(ticker_list)} tickers")

    for ticker in ticker_list:
        start_time = time.time()
        logging.info(f"🔄 START: Processing {ticker}")
        result = process_ticker(ticker)
        if result is not None:
            results.append(result)
            logging.info(f"✅ END: Successfully processed {ticker}")
        else:
            failures.append(ticker)
        elapsed = time.time() - start_time
        logging.info(f"⏱️ {ticker} processing time: {elapsed:.2f}s")

    if failures:
        logging.warning(f"❌ Failed tickers: {failures}")
    else:
        logging.info("🚀 All tickers processed successfully")

    df = pd.concat(results, ignore_index=True) if results else pd.DataFrame()
    return df, failures


def dry_run_cache_report(ticker_list):
    report = []

    for ticker in ticker_list:
        path = cache_path_for(ticker)
        if not os.path.exists(path):
            report.append((ticker, "❌ No cache"))
            continue

        try:
            df = pd.read_pickle(path)
            if df.empty or "Date" not in df.columns:
                report.append((ticker, "⚠️ Invalid or empty cache"))
                continue

            cache_date = pd.to_datetime(df["Date"].iloc[0]).date()
            age_days = (datetime.today().date() - cache_date).days
            status = "✅ Fresh" if age_days <= MAX_CACHE_AGE_DAYS else f"🔁 Stale ({age_days}d)"
            report.append((ticker, status))
        except Exception as e:
            report.append((ticker, f"💥 Error: {str(e)}"))

    return pd.DataFrame(report, columns=["Ticker", "Cache Status"])


def purge_stale_cache(max_age_days=7):
    from modules.core_utils.path_utils import DATA_DIR
    logging.info(f"🧹 Purging cache files older than {max_age_days} day(s)")

    now = datetime.today().date()
    purged = []

    for fname in os.listdir(DATA_DIR):
        if not fname.endswith(".pkl"):
            continue

        path = os.path.join(DATA_DIR, fname)
        try:
            df = pd.read_pickle(path)
            if "Date" not in df.columns or df.empty:
                os.remove(path)
                reason = "No Date or Empty"
                purged.append((fname, reason))
                logging.debug(f"🗑️ Removed {fname} — {reason}")
                continue

            date = pd.to_datetime(df["Date"].iloc[0]).date()
            age = (now - date).days
            if age > max_age_days:
                os.remove(path)
                reason = f"Stale ({age}d)"
                purged.append((fname, reason))
                logging.debug(f"🗑️ Removed {fname} — {reason}")

        except Exception as e:
            os.remove(path)
            reason = f"Corrupt: {e}"
            purged.append((fname, reason))
            logging.debug(f"🗑️ Removed {fname} — {reason}")

    logging.info(f"🧾 Purge complete. {len(purged)} file(s) removed.")
    return pd.DataFrame(purged, columns=["File", "Reason"]) if purged else pd.DataFrame(columns=["File", "Reason"])
