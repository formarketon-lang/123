
import streamlit as st

from data.benchmark_mapping import get_main_benchmarks


SECTORS = [
    "All Sectors",
    "Auto",
    "Banking",
    "Capital Goods",
    "Chemicals",
    "Consumer Discretionary",
    "Energy",
    "FMCG",
    "Healthcare",
    "IT",
    "Metals & Mining",
    "Realty",
    "Telecom",
    "Utilities",
]

MARKET_CAP_OPTIONS = [
    "All Market Caps",
    "Large Cap",
    "Mid Cap",
    "Small Cap",
]

EXCHANGE_OPTIONS = [
    "NSE",
    "BSE",
    "Both",
]

ACTIVE_DATA_SOURCE = "NSE Primary + Yahoo Secondary"


def _initialize_settings():
    """Initialize shared application settings safely."""

    defaults = {
        "data_source": ACTIVE_DATA_SOURCE,
        "settings_exchange": "NSE",
        "settings_start_date": None,
        "settings_end_date": None,
        "settings_benchmark": "Nifty 50",
        "settings_sector": "All Sectors",
        "settings_market_cap": "All Market Caps",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Migrate the old Yahoo-only label to the actual adapter.
    if st.session_state["data_source"] == "Yahoo Finance":
        st.session_state["data_source"] = ACTIVE_DATA_SOURCE


def render_settings_page():
    """Render verified market-data and scanner preferences."""

    _initialize_settings()

    st.header("Settings (Data)")
    st.caption(
        "TradeLab Pro · Shared Market Data Configuration"
    )

    # 1. Data Source
    st.subheader("1. Data Source")

    st.selectbox(
        "Active Market Data Adapter",
        [ACTIVE_DATA_SOURCE],
        key="data_source",
        help=(
            "NSE Primary is attempted first. "
            "Yahoo Finance is used as Secondary fallback."
        ),
    )

    st.success(
        "Active: NSE Primary → Yahoo Secondary"
    )

    st.caption(
        "NSE daily historical data is the primary source. "
        "Yahoo Finance is used only when NSE data is unavailable "
        "or the requested interval is unsupported."
    )

    st.info(
        "CSV / Excel, Broker API, Demo Data এবং অন্যান্য "
        "external providers এখনো এই Scanner-এর সঙ্গে "
        "সংযুক্ত নয়। এগুলোকে Active Source হিসেবে দেখানো হচ্ছে না।"
    )

    # 2. Exchange
    st.subheader("2. Exchange")

    exchange = st.selectbox(
        "Select Exchange",
        EXCHANGE_OPTIONS,
        key="settings_exchange",
    )

    if exchange == "NSE":
        st.success(
            "NSE is supported by the current verified Scanner."
        )
    else:
        st.warning(
            "BSE এবং Both এখনো Scanner-এ সক্রিয় নয়। "
            "বর্তমানে Relative Strength analysis শুধু "
            "verified NSE EQ Universe ব্যবহার করে।"
        )

    # 3. Historical Date Range
    st.subheader("3. Historical Date Range")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=st.session_state["settings_start_date"],
            key="settings_start_date",
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=st.session_state["settings_end_date"],
            key="settings_end_date",
        )

    valid_dates = True

    if start_date and end_date and start_date > end_date:
        st.error(
            "Start Date must be on or before End Date."
        )
        valid_dates = False

    elif bool(start_date) != bool(end_date):
        st.warning(
            "Choose both dates, or leave both dates empty."
        )
        valid_dates = False

    # 4. Main Benchmark
    st.subheader("4. Main Benchmark")

    benchmarks = get_main_benchmarks()

    if not benchmarks:
        st.error(
            "No configured Main Benchmark is available."
        )
        return

    if (
        st.session_state["settings_benchmark"]
        not in benchmarks
    ):
        st.session_state["settings_benchmark"] = (
            next(iter(benchmarks))
        )

    benchmark_name = st.selectbox(
        "Select Main Benchmark",
        list(benchmarks.keys()),
        key="settings_benchmark",
    )

    st.caption(
        f"Configured ticker: {benchmarks[benchmark_name]}"
    )

    # 5. Sector
    st.subheader("5. Sector")

    sector = st.selectbox(
        "Select Sector",
        SECTORS,
        key="settings_sector",
    )

    if sector == "FMCG":
        st.success(
            "FMCG has a configured sector benchmark. "
            "Official constituent verification is still required "
            "during scanner execution."
        )
    elif sector != "All Sectors":
        st.warning(
            "This sector does not currently have a verified "
            "sector benchmark mapping."
        )

    # 6. Market Capitalization
    st.subheader("6. Market Capitalization")

    market_cap = st.selectbox(
        "Market Cap Filter",
        MARKET_CAP_OPTIONS,
        key="settings_market_cap",
    )

    st.caption(
        "Classification uses the latest available official "
        "AMFI half-yearly data. Only ISIN and NSE Symbol "
        "verified matches are eligible."
    )

    # 7. Current Configuration
    st.divider()
    st.subheader("Current Configuration")

    st.write(f"**Data Source:** {ACTIVE_DATA_SOURCE}")
    st.write(f"**Exchange:** {exchange}")
    st.write(
        f"**Start Date:** {start_date or 'Not selected'}"
    )
    st.write(
        f"**End Date:** {end_date or 'Not selected'}"
    )
    st.write(f"**Main Benchmark:** {benchmark_name}")
    st.write(f"**Sector:** {sector}")
    st.write(f"**Market Capitalization:** {market_cap}")

    if valid_dates:
        st.success(
            "Settings values are valid and stored in the "
            "Streamlit session."
        )
    else:
        st.warning(
            "Date configuration is incomplete or invalid."
        )

    st.caption(
        "Note: These settings are shared session preferences. "
        "The next integration step will connect Exchange, "
        "Date Range and Benchmark directly to the "
        "Relative Strength Scanner."
    )
    
