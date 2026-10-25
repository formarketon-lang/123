import streamlit as st

SECTORS = [
    "None",
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


def render_relative_strength_page():
    st.header("Relative Strength")
    st.info(
        "Phase 1: layout scaffold only. Calculations, live data, results and charts "
        "will be added in later phases after their tests are in place."
    )

    st.subheader("Filters")
    st.selectbox("Sector", SECTORS, index=0, key="rs_sector")
    st.text_input(
        "Search stock name / symbol (optional)",
        value="",
        key="rs_stock_search",
        placeholder="e.g. HINDUNILVR",
    )

    st.toggle("Enable Market Cap filter", value=False, key="market_cap_enabled")
    if st.session_state.get("market_cap_enabled", False):
        st.multiselect(
            "Market Capitalization",
            ["Large Cap", "Mid Cap", "Small Cap"],
            key="market_cap_values",
        )

    st.subheader("Date-Based RS")
    st.toggle("Enable Date-Based RS", value=False, key="date_rs_enabled")
    if st.session_state.get("date_rs_enabled", False):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.date_input("Date I — Center", key="rs_date_i")
        with d2:
            st.date_input("Date II — Before", key="rs_date_ii")
        with d3:
            st.date_input("Date III — After", key="rs_date_iii")
        st.multiselect(
            "Date comparison",
            [
                "Date I ↔ Date II",
                "Date I ↔ Date III",
                "Date II ↔ Date III",
                "Date I ↔ Date II ↔ Date III",
            ],
            default=["Date I ↔ Date II"],
            key="rs_date_comparisons",
        )
        st.caption(
            "Holiday highlighting and nearest-trading-day validation will be implemented "
            "with the trading-calendar layer."
        )

    st.subheader("Average RS")
    st.toggle("Enable Average RS", value=False, key="average_rs_enabled")
    if st.session_state.get("average_rs_enabled", False):
        st.multiselect(
            "Lookback days",
            [20, 30, 50, 100],
            default=[20],
            key="average_rs_days",
        )
        st.number_input(
            "Custom lookback days (optional; 0 means unused)",
            min_value=0,
            max_value=2000,
            value=0,
            step=1,
            key="custom_rs_days",
        )

    st.selectbox(
        "Timeframe",
        ["1D", "5M", "15M", "30M", "60M"],
        index=0,
        key="rs_timeframe",
    )

    if st.button("Run", type="primary", key="rs_run"):
        st.warning(
            "The Run action is a placeholder in Phase 1. No market data is fetched "
            "and no results are calculated yet."
        )
