
"""
TradeLab Pro - Relative Strength Page

Verified NSE EQ universe with official AMFI Market Cap filtering.
Separate Stock vs Main Index and audited Sector comparisons.
Supports standard and custom calendar-day return windows.

BSE remains disabled until its official universe and validated
data adapter are available.
"""

from datetime import date, timedelta

import streamlit as st

from data.universe import load_nse_universe
from data.market_cap import (
    fetch_amfi_market_cap,
    enrich_nse_universe_with_amfi,
    filter_by_market_cap,
)
from data.benchmark_mapping import (
    MAIN_BENCHMARKS,
    get_sector_benchmark,
)
from core.rs_scanner import execute_scanner
from ui.rs_results import display_results


SECTORS = [
    "None",
    "FMCG",
]

MARKET_CAP_OPTIONS = [
    "All Market Caps",
    "Large Cap",
    "Mid Cap",
    "Small Cap",
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


@st.cache_data(ttl=21600, show_spinner=False)
def get_cached_amfi_market_cap():
    """Cache official AMFI half-yearly market-cap classification."""
    return fetch_amfi_market_cap()


def initialize_session():
    if "rs_last_run" not in st.session_state:
        st.session_state["rs_last_run"] = None

    if "settings_market_cap" not in st.session_state:
        st.session_state["settings_market_cap"] = "All Market Caps"


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

    # BSE fail-closed guard
    if exchange == "BSE":

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

    # 2. Market Cap setting
    st.subheader("2. Market Capitalization")

    # IMPORTANT:
    # Settings page and Relative Strength use the SAME session key.
    market_cap_filter = st.selectbox(
        "Market Cap Filter",
        MARKET_CAP_OPTIONS,
        key="settings_market_cap",
        help=(
            "AMFI-এর সর্বশেষ উপলব্ধ half-yearly classification "
            "অনুযায়ী NSE stocks filter করা হবে।"
        ),
    )

    st.caption(
        "AMFI classification half-yearly; এটি live daily market cap নয়। "
        "শুধু ISIN এবং NSE Symbol উভয়টি মিলে গেলে stock eligible হবে।"
    )

    # 3. Stock selection
    st.subheader("3. Stock Selection")

    sector = st.selectbox(
        "Select Sector",
        SECTORS,
        key="rs_sector",
    )

    universe = None
    market_cap_universe = None
    universe_symbols = []
    selected_symbols = []

    refresh_col, info_col = st.columns([1, 2])

    with refresh_col:
        if st.button(
            "Refresh NSE Universe",
            use_container_width=True,
        ):
            get_cached_nse_universe.clear()
            get_cached_amfi_market_cap.clear()

    try:
        with st.spinner("Verified NSE EQ Universe লোড হচ্ছে..."):

            # Keep the complete NSE universe for sector membership audit.
            universe = get_cached_nse_universe()

        eligible = universe.copy()

        # Apply official AMFI classification only when requested.
        if market_cap_filter != "All Market Caps":

            with st.spinner(
                "Official AMFI Market Cap classification যাচাই হচ্ছে..."
            ):

                amfi_data = get_cached_amfi_market_cap()

                market_cap_universe = enrich_nse_universe_with_amfi(
                    universe,
                    amfi_data,
                )

                eligible = filter_by_market_cap(
                    market_cap_universe,
                    market_cap_filter,
                )

            if eligible.empty:
                raise ValueError(
                    f"{market_cap_filter}-এ কোনো verified NSE EQ "
                    "stock পাওয়া যায়নি।"
                )

            st.info(
                f"AMFI Market Cap Filter: {market_cap_filter} | "
                f"Verified Matches: {len(eligible):,}"
            )

        # Only verified NSE EQ rows with ISIN are selectable.
        eligible = eligible[
            (
                eligible["Series"]
                .astype("string")
                .str.strip()
                .str.upper()
                == "EQ"
            )
            & eligible["ISIN"].notna()
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
                "Eligible NSE EQ Securities",
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

        universe = None
        market_cap_universe = None
        selected_symbols = []

        st.error(
            "NSE Universe অথবা Market Cap classification লোড "
            "করা যায়নি। এই অবস্থায় Scanner চালানো হবে না।"
        )

        st.caption(f"Technical detail: {error}")

    manual_symbols = st.text_area(
        "Manual Stock Symbols (Optional)",
        placeholder="MARICO, RELIANCE, INFY",
        help=(
            "Manual Symbol দিলে সেটিই অগ্রাধিকার পাবে। "
            "NSE Symbol অবশ্যই verified NSE EQ Universe-এ থাকতে হবে। "
            "Market Cap filter সক্রিয় থাকলে নির্বাচিত category-তেও "
            "থাকতে হবে।"
        ),
        key="rs_symbols",
    )

    if universe is not None:
        st.caption(
            "Manual Symbol না দিলে উপরে নির্বাচন করা NSE Stocks "
            "বিশ্লেষণ হবে। কোনো Stock নির্বাচন না করলে নির্বাচিত "
            "Sector-এর audited official membership থেকে Market Cap "
            "অনুযায়ী eligible stocks নেওয়া হবে।"
        )

    # 4. Benchmark selection
    st.divider()
    st.subheader("4. Benchmark Selection")

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

    # 5. Return period
    st.divider()
    st.subheader("5. Return Period")

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

    st.subheader("Custom Return Window")

    custom_days = st.number_input(
        "Custom Window (Calendar Days)",
        min_value=2,
        max_value=3650,
        value=45,
        step=1,
        key="rs_custom_window_days",
        help=(
            "উদাহরণ: 45 দিলে শেষ তারিখ থেকে 45 Calendar Days-এর "
            "Return Window তৈরি হবে।"
        ),
    )

    include_custom_window = st.checkbox(
        "Include Custom Window",
        value=False,
        key="rs_include_custom_window",
    )

    if include_custom_window:

        custom_token = f"CUSTOM_{int(custom_days)}D"

        if custom_token not in custom_windows:
            custom_windows.append(custom_token)

        st.info(
            f"Custom Window সক্রিয়: "
            f"{int(custom_days)} Calendar Days"
        )

    st.caption(
        "Selected Period, Standard Windows এবং সক্রিয় Custom Window "
        "আলাদাভাবে বিশ্লেষণ করা হবে।"
    )

    # 6. Run scanner
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
                        market_cap_filter=market_cap_filter,
                        market_cap_universe=market_cap_universe,
                    )

                    st.session_state["rs_last_run"] = new_result

                st.success(
                    "Analysis সম্পন্ন। "
                    "ফলাফল Session-এ সংরক্ষণ করা হয়েছে।"
                )

            except Exception as error:

                st.error(
                    f"Scanner চালানো যায়নি: {error}"
                )

    # 7. Persistent results
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
            "audited official membership ব্যবহার করুন। "
            "তারপর Run চাপুন।"
        )
