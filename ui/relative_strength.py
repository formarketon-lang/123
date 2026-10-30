"""
TradeLab Pro - Relative Strength Page

Handles user inputs, scanner execution and result persistence.
"""

import streamlit as st
from datetime import date, timedelta

from data.benchmark_mapping import (
    MAIN_BENCHMARKS,
    get_sector_benchmark,
)
from core.rs_scanner import execute_scanner
from ui.rs_results import display_results


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


def initialize_session():
    """Initialize persistent scanner result."""

    if "rs_last_run" not in st.session_state:
        st.session_state["rs_last_run"] = None


def render_relative_strength_page():

    initialize_session()

    st.header("Relative Strength Scanner")

    st.caption(
        "TradeLab Pro · NSE/BSE Cash Market · "
        "Stock vs Sector vs Main Index"
    )

    # 1. Stock Selection
    st.subheader("1. Stock Selection")

    sector = st.selectbox(
        "Select Sector",
        SECTORS,
        key="rs_sector",
    )

    manual_symbols = st.text_area(
        "Stock Symbols (Optional)",
        placeholder="HINDUNILVR, RELIANCE, INFY",
        help="একাধিক Symbol কমা অথবা নতুন লাইনে লিখুন।",
        key="rs_symbols",
    )

    exchange = st.selectbox(
        "Exchange",
        ["NSE", "BSE"],
        key="rs_exchange",
    )

    if sector == "FMCG" and not manual_symbols.strip():
        st.info(
            "FMCG Starter Universe: HINDUNILVR। "
            "এটি সম্পূর্ণ Sector Universe নয়।"
        )

    # 2. Benchmark Selection
    st.divider()
    st.subheader("2. Benchmark Selection")

    benchmark_name = st.selectbox(
        "Main Benchmark Index",
        list(MAIN_BENCHMARKS.keys()),
        key="rs_main_benchmark",
    )

    sector_benchmark_symbol = get_sector_benchmark(sector)

    if sector_benchmark_symbol:
        st.success(
            f"Verified Sector Benchmark: {sector}"
        )
    else:
        st.warning(
            "এই Sector-এর verified Index Mapping এখনো যুক্ত হয়নি। "
            "Sector Comparison বর্তমানে unavailable।"
        )

    # 3. Return Period
    st.divider()
    st.subheader("3. Return Period")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=365),
            key="rs_start",
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            key="rs_end",
        )

    custom_windows = st.multiselect(
        "Additional Return Windows",
        ["1M", "3M", "6M", "1Y"],
        default=["1M", "3M"],
        key="rs_windows",
    )

    st.caption(
        "Selected Period এবং নির্বাচিত অতিরিক্ত Windows "
        "আলাদাভাবে বিশ্লেষণ করা হবে।"
    )

    # 4. Run Scanner
    st.divider()

    run_button = st.button(
        "Run Relative Strength Scanner",
        type="primary",
        use_container_width=True,
    )

    if run_button:

        if start_date >= end_date:
            st.error(
                "Start Date অবশ্যই End Date-এর আগের হতে হবে।"
            )

        else:
            try:
                with st.spinner(
                    "Market Data সংগ্রহ এবং Relative Strength বিশ্লেষণ চলছে..."
                ):
                    new_result = execute_scanner(
                        sector=sector,
                        manual_symbols=manual_symbols,
                        exchange=exchange,
                        benchmark_name=benchmark_name,
                        sector_benchmark_symbol=sector_benchmark_symbol,
                        start_date=start_date,
                        end_date=end_date,
                        custom_windows=custom_windows,
                    )

                    st.session_state["rs_last_run"] = new_result

                st.success(
                    "Analysis সম্পন্ন। ফলাফল Session-এ সংরক্ষিত হয়েছে।"
                )

            except Exception as error:
                st.error(
                    f"Scanner চালানো যায়নি: {error}"
                )

    # 5. Persistent Results
    saved_result = st.session_state.get("rs_last_run")

    if saved_result is not None:

        st.divider()
        st.subheader("Last Successful Run")

        st.caption(
            "নিচের ফলাফলটি সর্বশেষ সম্পন্ন Analysis-এর। "
            "নতুন Run না করা পর্যন্ত এটি সংরক্ষিত থাকবে।"
        )

        display_results(saved_result)

    else:
        st.info(
            "Selection সম্পূর্ণ করে Run চাপুন। "
            "Analysis-এর ফলাফল এখানে দেখা যাবে।"
    )
    
