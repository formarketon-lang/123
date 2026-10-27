import streamlit as st


def render_settings_page():
    """TradeLab Pro - Data Settings UI."""

    st.header("Settings")
    st.caption("Configure market data preferences.")

    st.subheader("Data Source")

    data_source = st.selectbox(
        "Select Data Source",
        [
            "Yahoo Finance",
            "CSV / Excel",
            "Broker API",
            "Demo Data",
        ],
        key="data_source",
    )

    exchange = st.selectbox(
        "Exchange",
        ["NSE", "BSE", "Both"],
        key="exchange",
    )

    st.subheader("Date Range")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            key="data_start_date",
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            key="data_end_date",
        )

    st.subheader("Benchmark")

    benchmark = st.selectbox(
        "Select Benchmark",
        [
            "Nifty 50",
            "Nifty Next 50",
            "Nifty Midcap 150",
            "Nifty Smallcap 250",
            "Sensex",
        ],
        key="benchmark",
    )

    if start_date > end_date:
        st.error("Start Date must be on or before End Date.")
        return

    st.divider()

    st.write("### Current Configuration")

    st.write(f"**Data Source:** {data_source}")
    st.write(f"**Exchange:** {exchange}")
    st.write(f"**Start Date:** {start_date}")
    st.write(f"**End Date:** {end_date}")
    st.write(f"**Benchmark:** {benchmark}")

    st.info(
        "These settings define UI preferences. "
        "Live data-source integration will be handled "
        "by the Data Source Adapter architecture."
    )
