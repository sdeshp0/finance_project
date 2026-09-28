"""S&P 500 Signal Dashboard - single-page Streamlit app.
Run: streamlit run app.py
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from signals.data import load_prices, load_sp500
from signals.indicators import compute_indicators
from signals.summary import PRESETS, add_summary, build_table

st.set_page_config(page_title="S&P 500 Signal Dashboard", page_icon="📈", layout="wide")
st.title("📈 S&P 500 Signal Dashboard")
st.caption("Technical-indicator screener")


@st.cache_data(ttl=3600, show_spinner=False)
def get_table(tickers: tuple[str, ...], lookback: int) -> pd.DataFrame:
    return build_table(load_prices(tickers), lookback)


def price_chart(ticker: str, tickers: tuple[str, ...], rsi_low: int, rsi_high: int) -> go.Figure:
    df = compute_indicators(load_prices(tickers)[ticker])
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.6, 0.2, 0.2])
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
                                 close=df["Close"], name=ticker), row=1, col=1)
    for n, color in ((50, "#f39c12"), (200, "#3498db")):
        fig.add_trace(go.Scatter(x=df.index, y=df[f"SMA_{n}"], name=f"SMA {n}",
                                 line=dict(width=1.5, color=color)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#9b59b6")),
                  row=2, col=1)
    fig.add_hline(y=rsi_high, line_dash="dot", line_color="#e74c3c", row=2, col=1)
    fig.add_hline(y=rsi_low, line_dash="dot", line_color="#2ecc71", row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="MACD hist",
                         marker_color="#95a5a6"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal", line=dict(width=1)),
                  row=3, col=1)
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_layout(height=650, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=1.05))
    return fig


# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Universe")
    mode = st.radio("Select tickers by", ["S&P 500 sectors", "Custom list"], label_visibility="collapsed")
    meta = None
    if mode == "S&P 500 sectors":
        try:
            meta = load_sp500()
        except Exception as e:
            st.error(f"Could not load the S&P 500 list: {e}")
            st.stop()
        sectors = sorted(meta["GICS Sector"].unique())
        chosen = st.multiselect("Sectors", sectors, default=["Information Technology"])
        tickers = tuple(sorted(meta.loc[meta["GICS Sector"].isin(chosen), "Ticker"]))
    else:
        raw = st.text_area("Comma-separated tickers", "AAPL, MSFT, NVDA, AMZN, TSLA, JPM")
        tickers = tuple(sorted({t.strip().upper().replace(".", "-") for t in raw.split(",") if t.strip()}))

    st.header("Signals")
    rsi_low, rsi_high = st.slider("RSI oversold / overbought", 5, 95, (30, 70))
    lookback = st.slider("Crossover lookback (days)", 1, 10, 3,
                         help="A crossover counts if it happened within this many recent days.")
    preset = st.selectbox("Screen", list(PRESETS))

if not tickers:
    st.info("Pick at least one sector or enter some tickers.")
    st.stop()
if len(tickers) > 150:
    st.caption(f"{len(tickers)} tickers selected - the first load may take a little while.")

# ---------------- Data ----------------
try:
    with st.spinner(f"Loading {len(tickers)} tickers…"):
        table = get_table(tickers, lookback)
except Exception as e:
    st.error(f"Data load failed: {e}")
    st.stop()

missing = sorted(set(tickers) - set(table.index))
if missing:
    with st.expander(f"⚠️ {len(missing)} ticker(s) returned no data"):
        st.code(", ".join(missing))

table = add_summary(table, rsi_low, rsi_high)
if meta is not None:
    table = table.join(meta.set_index("Ticker")[["Security"]])
view = table[PRESETS[preset](table, rsi_low, rsi_high)]

# ---------------- Summary metrics ----------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tickers shown", f"{len(view)} / {len(table)}")
c2.metric("Bullish MACD/SMA crosses", int(((table["MACD_x"] > 0) | (table["SMA_x"] > 0)).sum()))
c3.metric("RSI oversold", int((table["RSI"] < rsi_low).sum()))
c4.metric("RSI overbought", int((table["RSI"] > rsi_high).sum()))
st.caption(f"Latest bar: {table['Date'].max():%Y-%m-%d}. Prices are split/dividend adjusted; data via Yahoo Finance, cached for 1 hour.")

# ---------------- Table ----------------
X = {1: "↑ Bull", -1: "↓ Bear", 0: "–"}
show = view.assign(MACD_x=view["MACD_x"].map(X), SMA_x=view["SMA_x"].map(X), CCI_x=view["CCI_x"].map(X))
cols = ["Security", "Close", "Ret_1d", "Ret_5d", "Ret_1m", "RSI", "MACD_x", "SMA_x", "CCI_x",
        "Streak", "Vol_Index", "From_52w_High", "Above_SMA200", "Signals"]
show = show[[c for c in cols if c in show.columns]].rename(columns={
    "Ret_1d": "1d", "Ret_5d": "5d", "Ret_1m": "1m", "MACD_x": "MACD", "SMA_x": "SMA 10/50",
    "CCI_x": "CCI", "Vol_Index": "Vol vs 50d", "From_52w_High": "vs 52w high",
    "Above_SMA200": "> SMA200"})


def _rsi_style(v):
    if pd.isna(v):
        return ""
    if v > rsi_high:
        return "background-color: rgba(231,76,60,.35)"
    return "background-color: rgba(46,204,113,.35)" if v < rsi_low else ""


def _ret_style(v):
    return "" if pd.isna(v) else ("color: #2ecc71" if v > 0 else "color: #e74c3c" if v < 0 else "")


fmt = {"Close": "{:.2f}", "1d": "{:+.2%}", "5d": "{:+.2%}", "1m": "{:+.2%}", "RSI": "{:.0f}",
       "Vol vs 50d": "{:.2f}x", "vs 52w high": "{:+.1%}", "Streak": "{:+d}"}
styled = (show.style.map(_rsi_style, subset=["RSI"]).map(_ret_style, subset=["1d", "5d", "1m"])
          .format({k: v for k, v in fmt.items() if k in show.columns}))

st.subheader("Signals")
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
    st.plotly_chart(price_chart(sel, tickers, rsi_low, rsi_high), width="stretch")
else:
    st.caption("👆 Click a row to see its chart.")
