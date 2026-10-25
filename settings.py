import streamlit as st

DATA_SOURCES = [
    "Yahoo Finance (yfinance)",
    "Finnhub",
    "Twelve Data",
    "Financial Modeling Prep (FMP)",
    "Tiingo",
    "Alpha Vantage",
    "Polygon.io",
    "Alpaca Markets",
    "Shoonya (Finvasia)",
    "Angel One (SmartAPI)",
    "Upstox API",
    "jugaad-data",
    "nselib",
    "SEC EDGAR",
    "FRED",
    "Custom API",
]

BENCHMARKS = [
    "NIFTY 50",
    "NIFTY Next 50",
    "NIFTY 100",
    "NIFTY 200",
    "NIFTY 500",
    "NIFTY Midcap 50",
    "NIFTY Midcap 100",
    "NIFTY Midcap 150",
    "NIFTY Smallcap 50",
    "NIFTY Smallcap 100",
    "NIFTY Smallcap 250",
    "NIFTY Microcap 250",
    "NIFTY Total Market",
    "NIFTY LargeMidcap 250",
]


def render_settings_page():
    st.header("Settings (Data)")
    st.info(
        "Phase 1: settings form and project foundation only. "
        "Live API connections will be added and tested in Phase 2."
    )

    st.subheader("A(i) Data Source")
    st.selectbox("Primary data source", DATA_SOURCES, key="data_source")
    st.caption(
        "Credentials must be stored as Streamlit secrets/environment variables, "
        "not committed to GitHub."
    )

    st.subheader("A(ii) Exchange")
    st.selectbox("Exchange", ["NSE", "BSE", "Both"], key="exchange")

    st.subheader("A(iii) Historical data range")
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input(
            "Start Date",
            value=None,
            key="start_date",
            help="Choose the first date included in the requested data range.",
        )
    with c2:
        end_date = st.date_input(
            "End Date",
            value=None,
            key="end_date",
            help="Choose the last date included in the requested data range.",
        )

    if start_date and end_date and start_date > end_date:
        st.error("Start Date must be on or before End Date.")

    st.subheader("A(iv) Broad Market Benchmark")
    st.selectbox("Main index / benchmark", BENCHMARKS, key="benchmark")

    st.caption("The selected values are currently UI settings; they do not fetch market data yet.")
