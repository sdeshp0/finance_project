import streamlit as st
import pandas as pd
from modules.data_pipeline import generate_dashboard_data

st.set_page_config(layout="wide")
st.title("📈 Technical Dashboard")

tickers = st.session_state.get("tickers", [])

st.sidebar.subheader("Signal Thresholds")
rsi_upper = st.sidebar.slider("RSI Overbought Threshold", 60, 90, 70)
rsi_lower = st.sidebar.slider("RSI Oversold Threshold", 10, 50, 30)

if not tickers:
    st.warning("Please select tickers on the Home page.")
    st.stop()

with st.spinner("Loading data..."):
    data, failures = generate_dashboard_data(tickers)

if failures:
    with st.expander("⚠️ Some tickers failed to load", expanded=False):
        st.warning(f"{len(failures)} tickers failed to download or process.")
        st.code("\n".join(failures), language="text")

if data.empty:
    st.warning("No data available. Try adjusting filters or check your connection.")
else:
    # Drop intermediate columns
    intermediate_cols = [
        "MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9",
        "daily_change", "52w_high", "52w_low", "Date"
    ] #+ [f"up_{n}_days" for n in range(2, 6)] + [f"down_{n}_days" for n in range(2, 6)]
    data.drop(columns=[col for col in intermediate_cols if col in data.columns], inplace=True, errors="ignore")

    # Reorder columns
    if "Signal Summary" in data.columns:
        cols = list(data.columns)
        vol_idx = cols.index("Volume") if "Volume" in cols else 0
        cols.insert(vol_idx + 1, cols.pop(cols.index("Signal Summary")))
        data = data[cols]

    CROSSOVER_MAP = {
        -1: "↓ Bearish",
        0: "– Neutral",
        1: "↑ Bullish"
    }

    # Convert Crossover columns to non-numeric indicators
    for col in ["MACD_crossover", "SMA_50_crossover", "CCI_crossover"]:
        if col in data.columns:
            data[col] = data[col].map(CROSSOVER_MAP)

    # Format and index
    numeric_cols = data.select_dtypes(include="number").columns
    data[numeric_cols] = data[numeric_cols].round(2)
    data.set_index("Ticker", inplace=True)

    # Stylers
    def highlight_column(col):
        name = col.name
        styles = []
        for val in col:
            if pd.isna(val): styles.append("")
            elif name == "RSI":
                styles.append("background-color: lightcoral" if val > rsi_upper
                              else "background-color: lightgreen" if val < rsi_lower else "")
            else:
                styles.append("")
        return styles

    def highlight_strong_signals(row):
        signals = row.get("Signal Summary", "")
        if "MACD ↑" in signals and "SMA50 ↑" in signals:
            return ["background-color: lightgreen"] * len(row)
        if "MACD ↓" in signals and "SMA50 ↓" in signals:
            return ["background-color: lightcoral"] * len(row)
        if "RSI Low" in signals or "RSI High" in signals:
            return ["background-color: khaki"] * len(row)
        return [""] * len(row)

    styled_df = (
        data.style
        .apply(highlight_column, axis=0)
        .apply(highlight_strong_signals, axis=1)
        .format(precision=2)
    )

    st.dataframe(styled_df, use_container_width=True)
    csv = data.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name="sp500_signals.csv",
        mime="text/csv",
        use_container_width=True,
    )
