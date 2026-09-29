"""S&P 500 Signal Dashboard - single-page Streamlit app.
Run: streamlit run app.py
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from signals.data import load_prices_safe, load_sp500_safe
from signals.indicators import compute_indicators
from signals.summary import GROUPS, PRESETS, add_summary, build_table

st.set_page_config(page_title="S&P 500 Signal Dashboard", page_icon="📈", layout="wide")
st.title("📈 S&P 500 Signal Dashboard")
st.caption("Technical-indicator screener")

PERIODS = {"6 months": "6mo", "1 year": "1y", "2 years": "2y", "5 years": "5y",
          "10 years": "10y", "Max": "max"}
OVERLAY_OPTIONS = {"SMA 10": "SMA_10", "SMA 50": "SMA_50", "SMA 100": "SMA_100",
                   "SMA 150": "SMA_150", "SMA 200": "SMA_200", "EMA 9": "EMA_9",
                   "EMA 18": "EMA_18", "VWAP": "VWAP", "Support": "Support",
                   "Resistance": "Resistance"}
DEFAULT_OVERLAYS = ["SMA 50", "SMA 200", "VWAP", "Support", "Resistance"]
PANEL_ORDER = ["RSI", "MACD", "ATR"]
OVERLAY_STYLE = {
    "SMA_10": dict(color="#1abc9c"), "SMA_50": dict(color="#f39c12"),
    "SMA_100": dict(color="#8e44ad"), "SMA_150": dict(color="#16a085"),
    "SMA_200": dict(color="#3498db"), "EMA_9": dict(color="#d35400", dash="dot"),
    "EMA_18": dict(color="#2c3e50", dash="dot"), "VWAP": dict(color="#e67e22", dash="dot"),
    "Support": dict(color="#2ecc71", dash="dash"), "Resistance": dict(color="#e74c3c", dash="dash"),
}


@st.cache_data(ttl=3600, show_spinner=False)
def get_table(tickers: tuple[str, ...], lookback: int, period: str):
    prices, source, asof = load_prices_safe(tickers, period)
    return build_table(prices, lookback), source, asof


@st.cache_data(ttl=3600, show_spinner=False)
def get_ticker_data(ticker: str, tickers: tuple[str, ...], period: str):
    prices, source, asof = load_prices_safe(tickers, period)
    return compute_indicators(prices[ticker]), source, asof


def build_chart(df, ticker: str, rsi_low: int, rsi_high: int,
                overlays: list[str], panels: list[str]) -> go.Figure:
    panels = [p for p in PANEL_ORDER if p in panels]  # canonical order regardless of pick order
    n_panels = len(panels)
    heights = [0.55] + [0.45 / n_panels] * n_panels if n_panels else [1.0]
    fig = make_subplots(rows=1 + n_panels, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=heights)

    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
                                 close=df["Close"], name=ticker), row=1, col=1)
    for label in overlays:
        col = OVERLAY_OPTIONS[label]
        style = OVERLAY_STYLE.get(col, {})
        fig.add_trace(go.Scatter(x=df.index, y=df[col], name=label,
                                 line=dict(width=1.5, **style)), row=1, col=1)

    row = 2
    if "RSI" in panels:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#9b59b6")),
                      row=row, col=1)
        fig.add_hline(y=rsi_high, line_dash="dot", line_color="#e74c3c", row=row, col=1)
        fig.add_hline(y=rsi_low, line_dash="dot", line_color="#2ecc71", row=row, col=1)
        row += 1
    if "MACD" in panels:
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="MACD hist",
                             marker_color="#95a5a6"), row=row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(width=1)),
                      row=row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", line=dict(width=1)),
                      row=row, col=1)
        row += 1
    if "ATR" in panels:
        fig.add_trace(go.Scatter(x=df.index, y=df["ATR"], name="ATR (14d)",
                                 line=dict(color="#7f8c8d")), row=row, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["ATR_SMA"], name="ATR avg (20d)",
                                 line=dict(color="#bdc3c7", dash="dot")), row=row, col=1)
        row += 1

    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(height=420 + 180 * n_panels, xaxis_rangeslider_visible=False,
                      margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=1.05))
    return fig


# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Universe")
    mode = st.radio("Select tickers by", ["S&P 500 sectors", "Custom list"], label_visibility="collapsed")
    meta = None
    if mode == "S&P 500 sectors":
        try:
            meta, meta_source, meta_asof = load_sp500_safe()
        except Exception as e:
            st.error(f"Could not load the S&P 500 list (live or snapshot): {e}")
            st.stop()
        if meta_source == "snapshot":
            st.caption(f"⚠️ Using a cached constituent list from {meta_asof or 'an earlier run'} "
                      "(Wikipedia unreachable).")
        sectors = sorted(meta["GICS Sector"].unique())
        chosen = st.multiselect("Sectors", sectors, default=["Information Technology"])
        tickers = tuple(sorted(meta.loc[meta["GICS Sector"].isin(chosen), "Ticker"]))
    else:
        raw = st.text_area("Comma-separated tickers", "AAPL, MSFT, NVDA, AMZN, TSLA, JPM")
        tickers = tuple(sorted({t.strip().upper().replace(".", "-") for t in raw.split(",") if t.strip()}))

    period_label = st.selectbox("History length", list(PERIODS), index=1,
                                help="How much price history to fetch. Longer history needed for "
                                     "e.g. SMA 200 to have a full warm-up, but is slower to load "
                                     "and, if Yahoo is unreachable, the offline snapshot only has 1 year.")
    period = PERIODS[period_label]

    st.header("Signals")
    rsi_low, rsi_high = st.slider("RSI oversold / overbought", 5, 95, (30, 70))
    lookback = st.slider("Crossover lookback (days)", 1, 10, 3,
                         help="A crossover counts if it happened within this many recent days.")
    preset_category = st.selectbox("Screen category", list(GROUPS))
    preset = st.selectbox("Screen", GROUPS[preset_category])
    query = st.text_input("Filter by signal text (optional)",
                          placeholder="e.g. breakout, VWAP, RSI high",
                          help="Further narrows the table to rows whose Signals text contains this.")

    st.header("Chart")
    overlays = st.multiselect("Overlay lines", list(OVERLAY_OPTIONS), default=DEFAULT_OVERLAYS)
    panels = st.multiselect("Lower panels", PANEL_ORDER, default=["RSI", "MACD"])

if not tickers:
    st.info("Pick at least one sector or enter some tickers.")
    st.stop()
if len(tickers) > 150 or period in ("5y", "10y", "max"):
    st.caption(f"{len(tickers)} tickers, {period_label.lower()} of history selected - "
              "the first load may take a little while.")

# ---------------- Data ----------------
try:
    with st.spinner(f"Loading {len(tickers)} tickers…"):
        table, data_source, data_asof = get_table(tickers, lookback, period)
except Exception as e:
    st.error(f"Data load failed (live and snapshot both unavailable): {e}")
    st.stop()

if data_source == "snapshot":
    st.warning(f"⚠️ Live price data is unavailable right now (Yahoo Finance may be rate-limiting "
              f"or unreachable). Showing a cached snapshot from **{data_asof or 'an earlier run'}**.")

missing = sorted(set(tickers) - set(table.index))
if missing:
    with st.expander(f"⚠️ {len(missing)} ticker(s) returned no data"):
        st.code(", ".join(missing))

table = add_summary(table, rsi_low, rsi_high)
if meta is not None:
    table = table.join(meta.set_index("Ticker")[["Security"]])

view = table[PRESETS[preset](table, rsi_low, rsi_high)]
if query:
    view = view[view["Signals"].str.contains(query, case=False, na=False, regex=False)]

# ---------------- Summary metrics ----------------
r1c1, r1c2, r1c3, r1c4 = st.columns(4)
r1c1.metric("Tickers shown", f"{len(view)} / {len(table)}")
r1c2.metric("Bullish bias", int((table["Bias"] == "Bullish").sum()))
r1c3.metric("Bearish bias", int((table["Bias"] == "Bearish").sum()))
r1c4.metric("Above VWAP", f"{(table['Close'] > table['VWAP']).mean():.0%}")

r2c1, r2c2, r2c3, r2c4 = st.columns(4)
r2c1.metric("Resistance breakouts", int((table["Resistance_x"] > 0).sum()))
r2c2.metric("Support breakdowns", int((table["Support_x"] < 0).sum()))
r2c3.metric("RSI oversold", int((table["RSI"] < rsi_low).sum()))
r2c4.metric("RSI overbought", int((table["RSI"] > rsi_high).sum()))

st.caption(f"Latest bar: {table['Date'].max():%Y-%m-%d}. Prices are split/dividend adjusted; "
          "data via Yahoo Finance, cached for 1 hour. VWAP is a 20-day rolling volume-weighted "
          "average (an approximation - true VWAP needs intraday data). Support/resistance are "
          "20-day Donchian-style channel levels.")

# ---------------- Table ----------------
X = {1: "↑ Bull", -1: "↓ Bear", 0: "–"}
RX = {1: "↑ Breakout", -1: "↓ Back below", 0: "–"}
SX = {1: "↑ Bounce", -1: "↓ Breakdown", 0: "–"}
AX = {1: "↑ Expanding", -1: "↓ Contracting", 0: "–"}
show = view.assign(
    MACD_x=view["MACD_x"].map(X), SMA_x=view["SMA_x"].map(X), CCI_x=view["CCI_x"].map(X),
    VWAP_x=view["VWAP_x"].map(X), EMA_x=view["EMA_x"].map(X), SMA150_x=view["SMA150_x"].map(X),
    Resistance_x=view["Resistance_x"].map(RX), Support_x=view["Support_x"].map(SX),
    ATR_x=view["ATR_x"].map(AX),
)
cols = ["Security", "Close", "Ret_1d", "Ret_5d", "Ret_1m", "RSI",
        "MACD_x", "SMA_x", "CCI_x", "VWAP_x", "EMA_x",
        "Support", "Resistance", "VWAP", "SMA_150", "ATR",
        "Support_x", "Resistance_x", "SMA150_x", "ATR_x",
        "Streak", "Vol_Index", "From_52w_High", "Above_SMA200", "Bias", "Signals"]
show = show[[c for c in cols if c in show.columns]].rename(columns={
    "Ret_1d": "1d", "Ret_5d": "5d", "Ret_1m": "1m", "MACD_x": "MACD", "SMA_x": "SMA 10/50",
    "CCI_x": "CCI", "VWAP_x": "VWAP x", "EMA_x": "EMA 9/18", "SMA_150": "SMA150",
    "SMA150_x": "SMA150 x", "Support_x": "Support x", "Resistance_x": "Resistance x",
    "ATR_x": "ATR x", "Vol_Index": "Vol vs 50d", "From_52w_High": "vs 52w high",
    "Above_SMA200": "> SMA200"})


def _rsi_style(v):
    if pd.isna(v):
        return ""
    if v > rsi_high:
        return "background-color: rgba(231,76,60,.35)"
    return "background-color: rgba(46,204,113,.35)" if v < rsi_low else ""


def _ret_style(v):
    return "" if pd.isna(v) else ("color: #2ecc71" if v > 0 else "color: #e74c3c" if v < 0 else "")


def _row_style(row):
    color = {"Bullish": "background-color: rgba(46,204,113,.12)",
             "Bearish": "background-color: rgba(231,76,60,.12)"}.get(row.get("Bias"), "")
    return [color] * len(row)


fmt = {"Close": "{:.2f}", "1d": "{:+.2%}", "5d": "{:+.2%}", "1m": "{:+.2%}", "RSI": "{:.0f}",
       "Support": "{:.2f}", "Resistance": "{:.2f}", "VWAP": "{:.2f}", "SMA150": "{:.2f}",
       "ATR": "{:.2f}", "Vol vs 50d": "{:.2f}x", "vs 52w high": "{:+.1%}", "Streak": "{:+d}"}
styled = (show.style.apply(_row_style, axis=1)
          .map(_rsi_style, subset=["RSI"]).map(_ret_style, subset=["1d", "5d", "1m"])
          .format({k: v for k, v in fmt.items() if k in show.columns}))

st.subheader("Signals")
st.caption("Rows are tinted by overall Bias (net of all crossovers + streak). "
          "Use the Screen preset or the signal-text filter in the sidebar to narrow further.")
event = st.dataframe(styled, on_select="rerun", selection_mode="single-row",
                     width="stretch", height=430)
st.download_button("📥 Download CSV", show.reset_index().to_csv(index=False).encode("utf-8"),
                   file_name="sp500_signals.csv", mime="text/csv")

# ---------------- Drill-down ----------------
rows = event.selection.rows
if rows:
    sel = show.index[rows[0]]
    label = f"{sel} - {show.loc[sel, 'Security']}" if "Security" in show.columns else sel
    st.subheader(label)
    try:
        df_full, chart_source, chart_asof = get_ticker_data(sel, tickers, period)
    except Exception as e:
        st.error(f"Could not load chart data for {sel}: {e}")
    else:
        if chart_source == "snapshot":
            st.caption(f"⚠️ Chart is from the cached snapshot ({chart_asof or 'an earlier run'}), "
                      f"limited to ~1 year of history regardless of the History length setting.")
        if overlays or panels:
            st.plotly_chart(build_chart(df_full, sel, rsi_low, rsi_high, overlays, panels),
                            width="stretch")
        else:
            st.info("No overlay lines or panels selected - pick some under Chart in the sidebar.")
        st.download_button(f"📥 Download all data for {sel}",
                           df_full.reset_index().rename(columns={"index": "Date"})
                           .to_csv(index=False).encode("utf-8"),
                           file_name=f"{sel}_data.csv", mime="text/csv")
else:
    st.caption("👆 Click a row to see its chart.")
