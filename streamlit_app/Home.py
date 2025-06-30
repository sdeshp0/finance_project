import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd
from modules.core_utils.config_loader import load_config
from modules.core_utils.decorators import cache_data
from modules.data_loader import load_sp500_table
from modules.data_pipeline import dry_run_cache_report, purge_stale_cache, initialize_logging
initialize_logging()

st.set_page_config(layout="wide")
st.title("📊 Stock Selector")


@st.cache_resource
def run_startup_purge():
    config = load_config()
    if config.get("purge_on_startup", False):
        return purge_stale_cache(max_age_days=0)
    return pd.DataFrame()


purge_result = run_startup_purge()
if not purge_result.empty:
    print(f"[CLEANUP] Purged {len(purge_result)} cache file(s) at startup.")


@cache_data
def get_sp500_metadata():
    return load_sp500_table()


option = st.radio("Choose how to select tickers:", ["S&P 500 Filters", "Custom Tickers"])

if option == "S&P 500 Filters":
    sp500_table = get_sp500_metadata()
    list_sectors = sorted(sp500_table["GICS Sector"].unique())

    with st.expander("Select S&P 500 Sectors", expanded=True):
        sectorSelect = st.container()
        allSectors = st.checkbox("Select All GICS Sectors", value=True)
        if allSectors:
            selected_sector = list_sectors
        else:
            selected_sector = sectorSelect.multiselect("Sectors", list_sectors)

        list_subsectors = sorted(
            sp500_table[sp500_table["GICS Sector"].isin(selected_sector)]["GICS Sub-Industry"].unique()
        )

        subsectorSelect = st.container()
        allSubsectors = st.checkbox("Select All GICS Sub-Industries", value=True)
        if allSubsectors:
            selected_subsector = list_subsectors
        else:
            selected_subsector = subsectorSelect.multiselect("Sub-Industries", list_subsectors)

    tickers = sp500_table[
        sp500_table["GICS Sector"].isin(selected_sector)
        & sp500_table["GICS Sub-Industry"].isin(selected_subsector)
    ]["Ticker"].tolist()

    st.session_state["tickers"] = tickers

else:
    user_input = st.text_area(
        "Enter comma-separated tickers (e.g. AAPL, MSFT, TSLA):",
        placeholder="Type your tickers here…"
    )
    if user_input:
        tickers = [t.strip().upper() for t in user_input.split(",") if t.strip()]
        st.session_state["tickers"] = tickers

if "tickers" in st.session_state and st.session_state["tickers"]:
    st.success(f"{len(st.session_state['tickers'])} ticker(s) selected.")
    with st.expander("List Tickers"):
        st.write(st.session_state["tickers"])

    with st.expander("📦 Check Cache Status (Dry Run)", expanded=False):

        if st.button("Run Cache Check"):
            cache_report_df = dry_run_cache_report(st.session_state["tickers"])
            st.dataframe(cache_report_df, use_container_width=True)

        max_age = st.slider("Delete cache older than (days):", min_value=0, max_value=30, value=7)
        if st.button("Run Cache Purge"):
            purge_result = purge_stale_cache(max_age)
            if purge_result.empty:
                st.success("No stale cache found!")
            else:
                st.warning(f"Purged {len(purge_result)} file(s):")
                st.dataframe(purge_result, use_container_width=True)
else:
    st.info("No tickers selected yet.")

