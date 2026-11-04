
import streamlit as st

from data.benchmark_mapping import get_main_benchmarks


SECTORS = [
    "All Sectors", "Auto", "Banking", "Capital Goods",
    "Chemicals", "Consumer Discretionary", "Energy",
    "FMCG", "Healthcare", "IT", "Metals & Mining",
    "Realty", "Telecom", "Utilities",
]

MARKET_CAP_OPTIONS = [
    "All Market Caps", "Large Cap", "Mid Cap", "Small Cap",
]


def render_settings_page():
    """Render validated market-data preferences."""

    st.header("Settings (Data)")
    st.caption("Configure TradeLab Pro market-data preferences.")

    st.subheader("1. Data Source")
    data_source = st.selectbox(
        "Select Data Source",
        ["Yahoo Finance", "CSV / Excel", "Broker API", "Demo Data"],
        key="data_source",
    )

    if data_source == "Yahoo Finance":
        st.success("Yahoo Finance historical adapter is available.")
    elif data_source == "CSV / Excel":
        st.info("CSV / Excel import is not connected yet.")
    elif data_source == "Broker API":
        st.info("Broker API integration is not connected yet.")
    else:
        st.warning("Demo data is not verified market data.")

    st.subheader("2. Exchange")
    exchange = st.selectbox(
        "Exchange",
        ["NSE", "BSE", "Both"],
        key="settings_exchange",
    )

    st.subheader("3. Historical Date Range")
    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=None,
            key="settings_start_date",
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=None,
            key="settings_end_date",
        )

    valid_dates = True

    if start_date and end_date and start_date > end_date:
        st.error("Start Date must be on or before End Date.")
        valid_dates = False
    elif bool(start_date) != bool(end_date):
        st.warning("Choose both dates, or leave both empty.")

    st.subheader("4. Main Benchmark")
    benchmarks = get_main_benchmarks()

    benchmark_name = st.selectbox(
        "Select configured benchmark",
        list(benchmarks.keys()),
        key="settings_benchmark",
    )

    st.caption(f"Yahoo ticker mapping: {benchmarks[benchmark_name]}")

    st.subheader("5. Sector")
    sector = st.selectbox(
        "Select Sector",
        SECTORS,
        key="settings_sector",
    )

    st.caption(
        "Sector selection is a preference. "
        "Not every sector has a verified index mapping."
    )

    st.subheader("6. Market Capitalization")
    market_cap = st.selectbox(
        "Market Cap Filter",
        MARKET_CAP_OPTIONS,
        key="settings_market_cap",
    )

    st.caption(
        "Market-cap filtering requires a verified stock universe "
        "and market-cap data source."
    )

    st.divider()
    st.subheader("Current Configuration")

    if valid_dates and bool(start_date) == bool(end_date):
        st.write(f"**Data Source:** {data_source}")
        st.write(f"**Exchange:** {exchange}")
        st.write(f"**Start Date:** {start_date or 'Not selected'}")
        st.write(f"**End Date:** {end_date or 'Not selected'}")
        st.write(f"**Main Benchmark:** {benchmark_name}")
        st.write(f"**Sector:** {sector}")
        st.write(f"**Market Capitalization:** {market_cap}")

    st.info(
        "These controls currently save UI selections in the Streamlit "
        "session. Only Yahoo Finance historical downloads are available. "
        "CSV import and broker connections are not activated yet."
    )
    
