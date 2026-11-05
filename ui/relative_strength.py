
"""
TradeLab Pro - Relative Strength Page

Select stocks from the verified NSE EQ universe,
then run separate Main Index and audited Sector comparisons.

BSE scanner remains disabled until official BSE universe
verification and a validated BSE data adapter are available.
"""

from datetime import date, timedelta

import streamlit as st

from data.universe import load_nse_universe
from data.benchmark_mapping import (
    MAIN_BENCHMARKS,
    get_sector_benchmark,
)
from core.rs_scanner import execute_scanner
from ui.rs_results import display_results


# Only FMCG currently has an official constituent source
# configured for live NSE MII membership auditing.
SECTORS = [
    "None",
    "FMCG",
]


BSE_DISABLED_MESSAGE = (
    "BSE Scanner বন্ধ রাখা হয়েছে। "
    "Official verified BSE Universe এবং validated BSE Data Adapter "
    "প্রস্তুত না হওয়া পর্যন্ত BSE Stock Analysis চালানো যাবে না।"
)


@st.cache_data(ttl=21600, show_spinner=False)
def get_cached_nse_universe():
    """Cache verified NSE EQ universe for six hours."""
    return load_nse_universe()


def initialize_session():
    if "rs_last_run" not in st.session_state:
        st.session_state["rs_last_run"] = None


def render_relative_strength_page():

    initialize_session()

    st.header("Relative Strength Scanner")
    st.caption(
        "TradeLab Pro · Verified NSE Universe · "
        "Stock vs Main Index vs Audited Sector"
    )

    # 1. Exchange selection
    st.subheader("1. Exchange Selection")

    exchange = st.selectbox(
        "Select Exchange",
        ["NSE", "BSE"],
        key="rs_exchange",
    )

    # BSE FAIL-CLOSED UI GUARD
    # Do not display manual symbols, benchmark controls,
    # date controls, or Run button for BSE.
    if exchange == "BSE":

        # Hide any previously displayed result while BSE is selected.
        st.session_state["rs_last_run"] = None

        st.error(BSE_DISABLED_MESSAGE)

        st.warning(
            "BSE Universe Verification, Official ISIN Mapping এবং "
            "BSE Data Adapter সম্পূর্ণভাবে যাচাই না হওয়া পর্যন্ত "
            "এই Exchange নিষ্ক্রিয় থাকবে।"
        )

        st.info(
            "বর্তমানে Relative Strength Scanner শুধু "
            "Verified NSE EQ Universe-এর জন্য উপলব্ধ।"
        )

        return

    # 2. Stock selection (NSE only)
    st.subheader("2. Stock Selection")

    sector = st.selectbox(
        "Select Sector",
        SECTORS,
        key="rs_sector",
    )

    universe = None
    universe_symbols = []
    selected_symbols = []

    refresh_col, info_col = st.columns([1, 2])

    with refresh_col:
        if st.button(
            "Refresh NSE Universe",
            use_container_width=True,
        ):
            get_cached_nse_universe.clear()

    try:
        with st.spinner(
            "Verified NSE EQ Universe লোড হচ্ছে..."
        ):
            universe = get_cached_nse_universe()

        eligible = universe[
            (universe["Series"].astype("string").str.upper() == "EQ")
            & universe["ISIN"].notna()
        ].copy()

        universe_symbols = sorted(
            eligible["Symbol"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .loc[lambda values: values != ""]
            .unique()
            .tolist()
        )

        with info_col:
            st.metric(
                "Verified NSE EQ Securities",
                f"{len(universe_symbols):,}",
            )

        selected_symbols = st.multiselect(
            "Select Stocks from NSE Universe",
            options=universe_symbols,
            default=[],
            help=(
                "Symbol লিখে Search করুন এবং এক বা একাধিক "
                "Stock নির্বাচন করুন।"
            ),
            key="rs_universe_symbols",
        )

    except Exception as error:
        selected_symbols = []

        st.error(
            "NSE Universe লোড করা যায়নি। "
            "এই অবস্থায় NSE Scanner চালানো হবে না।"
        )

        st.caption(f"Technical detail: {error}")

    manual_symbols = st.text_area(
        "Manual Stock Symbols (Optional)",
        placeholder="MARICO, RELIANCE, INFY",
        help=(
            "Manual Symbol দিলে সেটিই অগ্রাধিকার পাবে। "
            "NSE Symbol অবশ্যই verified NSE EQ Universe-এ থাকতে হবে।"
        ),
        key="rs_symbols",
    )

    if universe is not None:
        st.caption(
            "Manual Symbol না দিলে উপরে নির্বাচন করা NSE Stocks "
            "বিশ্লেষণ হবে। কোনো Stock নির্বাচন না করলে নির্বাচিত "
            "Sector-এর live audited official membership ব্যবহার হবে।"
        )

    # 3. Benchmark selection
    st.divider()
    st.subheader("3. Benchmark Selection")

    benchmark_name = st.selectbox(
        "Main Benchmark Index",
        list(MAIN_BENCHMARKS.keys()),
        key="rs_main_benchmark",
    )

    sector_benchmark_symbol = get_sector_benchmark(sector)

    if sector_benchmark_symbol:
        st.success(
            f"Configured Sector Benchmark: "
            f"{sector} ({sector_benchmark_symbol})"
        )

        st.caption(
            "Sector Comparison চালানোর আগে official constituent "
            "membership এবং NSE MII Symbol/ISIN audit যাচাই করা হবে।"
        )

    else:
        st.warning(
            "এই Sector-এর verified Index Mapping নেই। "
            "Sector Comparison unavailable থাকবে; "
            "Main Index Comparison চলতে পারবে।"
        )

    # 4. Return period
    st.divider()
    st.subheader("4. Return Period")

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

    # 5. Run scanner
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

        elif universe is None:
            st.error(
                "Verified NSE Universe পাওয়া যায়নি। "
                "প্রথমে Universe Connection ঠিক করুন।"
            )

        else:
            try:
                with st.spinner(
                    "Market Data সংগ্রহ এবং Relative Strength "
                    "বিশ্লেষণ চলছে..."
                ):

                    new_result = execute_scanner(
                        sector=sector,
                        manual_symbols=manual_symbols,
                        exchange="NSE",
                        benchmark_name=benchmark_name,
                        sector_benchmark_symbol=sector_benchmark_symbol,
                        start_date=start_date,
                        end_date=end_date,
                        custom_windows=custom_windows,
                        selected_symbols=selected_symbols,
                        universe=universe,
                    )

                    st.session_state["rs_last_run"] = new_result

                st.success(
                    "Analysis সম্পন্ন। "
                    "ফলাফল Session-এ সংরক্ষিত হয়েছে।"
                )

            except Exception as error:
                st.error(
                    f"Scanner চালানো যায়নি: {error}"
                )

    # 6. Persistent results
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
            "NSE Universe থেকে Stock নির্বাচন করুন অথবা "
            "Manual Symbol দিন। অথবা FMCG নির্বাচন করে "
            "live audited membership ব্যবহার করুন। "
            "তারপর Run চাপুন।"
        )
