"""
TradeLab Pro - Relative Strength Page

Settings-driven NSE Relative Strength Scanner.
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
    get_main_benchmarks,
    get_sector_benchmark,
)
from core.rs_scanner import execute_scanner
from ui.rs_results import display_results
from ui.settings import (
    SECTORS as SETTINGS_SECTORS,
    MARKET_CAP_OPTIONS,
    EXCHANGE_OPTIONS,
)


BSE_DISABLED_MESSAGE = (
    "BSE Scanner বন্ধ রাখা হয়েছে। "
    "Official verified BSE Universe এবং validated BSE Data Adapter "
    "প্রস্তুত না হওয়া পর্যন্ত BSE Stock Analysis চালানো যাবে না।"
)

UNSUPPORTED_EXCHANGE_MESSAGE = (
    "বর্তমানে Relative Strength Scanner শুধু NSE সমর্থন করে। "
    "BSE এবং Both নির্বাচন করলে Scanner চালানো হবে না।"
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
    """Initialize shared Settings and scanner session values."""

    defaults = {
        "rs_last_run": None,
        "data_source": "NSE Primary + Yahoo Secondary",
        "settings_exchange": "NSE",
        "settings_start_date": None,
        "settings_end_date": None,
        "settings_benchmark": "Nifty 50",
        "settings_sector": "All Sectors",
        "settings_market_cap": "All Market Caps",
        "rs_symbols": "",
        "rs_universe_symbols": [],
        "rs_windows": ["1M", "3M"],
        "rs_custom_window_days": 45,
        "rs_include_custom_window": False,
    }

    # Migrate previous scanner selections if shared Settings
    # keys have not been initialized yet.
    migrations = {
        "settings_exchange": "rs_exchange",
        "settings_benchmark": "rs_main_benchmark",
        "settings_sector": "rs_sector",
        "settings_start_date": "rs_start",
        "settings_end_date": "rs_end",
    }

    for new_key, old_key in migrations.items():
        if (
            new_key not in st.session_state
            and old_key in st.session_state
        ):
            st.session_state[new_key] = st.session_state[old_key]

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # If Settings dates are both empty, initialize a visible
    # one-year default range for the Scanner.
    if (
        st.session_state["settings_start_date"] is None
        and st.session_state["settings_end_date"] is None
    ):
        st.session_state["settings_start_date"] = (
            date.today() - timedelta(days=365)
        )
        st.session_state["settings_end_date"] = date.today()


def render_relative_strength_page():

    initialize_session()

    st.header("Relative Strength Scanner")
    st.caption(
        "TradeLab Pro · Settings-driven configuration · "
        "Verified NSE Universe"
    )

    # ---------------------------------------------------------
    # 1. Shared Exchange setting
    # ---------------------------------------------------------

    st.subheader("1. Exchange Selection")

    exchange = st.selectbox(
        "Select Exchange",
        EXCHANGE_OPTIONS,
        key="settings_exchange",
    )

    if exchange != "NSE":

        st.session_state["rs_last_run"] = None

        st.error(
            BSE_DISABLED_MESSAGE
            if exchange == "BSE"
            else UNSUPPORTED_EXCHANGE_MESSAGE
        )

        st.warning(
            "NSE ছাড়া অন্য Exchange-এর জন্য verified universe "
            "এবং validated data adapter এখনো সক্রিয় নয়।"
        )

        return

    st.success("NSE verified Scanner সক্রিয়।")

    # ---------------------------------------------------------
    # 2. Shared Market Cap setting
    # ---------------------------------------------------------

    st.subheader("2. Market Capitalization")

    market_cap_filter = st.selectbox(
        "Market Cap Filter",
        MARKET_CAP_OPTIONS,
        key="settings_market_cap",
        help=(
            "Settings (Data) এবং Relative Strength একই "
            "Market Cap setting ব্যবহার করছে।"
        ),
    )

    st.caption(
        "AMFI-এর সর্বশেষ উপলব্ধ half-yearly classification "
        "ব্যবহার করা হবে। ISIN এবং NSE Symbol verified match "
        "না হলে Stock eligible হবে না।"
    )

    # ---------------------------------------------------------
    # 3. Shared Sector setting
    # ---------------------------------------------------------

    st.subheader("3. Sector Selection")

    sector_setting = st.selectbox(
        "Select Sector",
        SETTINGS_SECTORS,
        key="settings_sector",
    )

    # All Sectors means no verified sector benchmark is selected.
    sector = (
        None
        if sector_setting == "All Sectors"
        else sector_setting
    )

    sector_benchmark_symbol = get_sector_benchmark(sector)

    if sector_benchmark_symbol:

        st.success(
            f"Verified Sector Benchmark: "
            f"{sector_setting} ({sector_benchmark_symbol})"
        )

        st.caption(
            "Sector Comparison-এর আগে official constituent "
            "membership এবং NSE MII Symbol/ISIN audit যাচাই হবে।"
        )

    else:

        st.warning(
            f"{sector_setting}-এর verified Sector Benchmark Mapping "
            "নেই। Sector Comparison unavailable থাকবে। "
            "Main Index Comparison চালানো যাবে।"
        )

    # ---------------------------------------------------------
    # 4. Verified NSE universe
    # ---------------------------------------------------------

    st.subheader("4. Stock Selection")

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
            universe = get_cached_nse_universe()

        eligible = universe.copy()

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
                    "Stock পাওয়া যায়নি।"
                )

            st.info(
                f"AMFI Market Cap Filter: {market_cap_filter} | "
                f"Verified Matches: {len(eligible):,}"
            )

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
                "এক বা একাধিক verified NSE Stock নির্বাচন করুন।"
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
            "Manual Symbol দিলে সেটি অগ্রাধিকার পাবে। "
            "Symbol অবশ্যই verified NSE EQ Universe-এ থাকতে হবে। "
            "Market Cap Filter সক্রিয় থাকলে নির্বাচিত category-তেও "
            "থাকতে হবে।"
        ),
        key="rs_symbols",
    )

    # ---------------------------------------------------------
    # 5. Shared Main Benchmark
    # ---------------------------------------------------------

    st.divider()
    st.subheader("5. Main Benchmark")

    benchmarks = get_main_benchmarks()

    if not benchmarks:
        st.error("কোনো configured Main Benchmark পাওয়া যায়নি।")
        return

    if st.session_state["settings_benchmark"] not in benchmarks:
        st.session_state["settings_benchmark"] = next(
            iter(benchmarks)
        )

    benchmark_name = st.selectbox(
        "Main Benchmark Index",
        list(benchmarks.keys()),
        key="settings_benchmark",
    )

    st.caption(
        f"Configured ticker: {benchmarks[benchmark_name]}"
    )

    # ---------------------------------------------------------
    # 6. Shared Settings Date Range
    # ---------------------------------------------------------

    st.divider()
    st.subheader("6. Historical Date Range")

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

    if start_date and end_date and start_date >= end_date:
        st.error(
            "Start Date অবশ্যই End Date-এর আগের হতে হবে।"
        )

    elif bool(start_date) != bool(end_date):
        st.warning(
            "Settings-এ Start Date এবং End Date দুটিই নির্বাচন করুন।"
        )

    # ---------------------------------------------------------
    # 7. Return windows
    # ---------------------------------------------------------

    st.divider()
    st.subheader("7. Return Period")

    custom_windows = st.multiselect(
        "Additional Return Windows",
        ["1M", "3M", "6M", "1Y"],
        default=["1M", "3M"],
        key="rs_windows",
    )

    custom_days = st.number_input(
        "Custom Window (Calendar Days)",
        min_value=2,
        max_value=3650,
        value=45,
        step=1,
        key="rs_custom_window_days",
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
            f"Custom Window সক্রিয়: {int(custom_days)} Calendar Days"
        )

    st.caption(
        "Selected Period, Standard Windows এবং Custom Window "
        "আলাদাভাবে বিশ্লেষণ করা হবে।"
    )

    # ---------------------------------------------------------
    # 8. Settings summary
    # ---------------------------------------------------------

    st.divider()
    st.subheader("Active Scanner Configuration")

    st.write(f"**Data Source:** {st.session_state['data_source']}")
    st.write(f"**Exchange:** {exchange}")
    st.write(f"**Market Cap:** {market_cap_filter}")
    st.write(f"**Sector:** {sector_setting}")
    st.write(f"**Main Benchmark:** {benchmark_name}")
    st.write(f"**Start Date:** {start_date}")
    st.write(f"**End Date:** {end_date}")

    # ---------------------------------------------------------
    # 9. Run scanner
    # ---------------------------------------------------------

    st.divider()

    run_button = st.button(
        "Run Relative Strength Scanner",
        type="primary",
        use_container_width=True,
    )

    if run_button:

        if not start_date or not end_date:

            st.error(
                "Settings-এ সম্পূর্ণ Date Range নির্বাচন করুন।"
            )

        elif start_date >= end_date:

            st.error(
                "Start Date অবশ্যই End Date-এর আগের হতে হবে।"
            )

        elif universe is None:

            st.error(
                "Verified NSE Universe পাওয়া যায়নি। "
                "প্রথমে Universe Connection ঠিক করুন।"
            )

        elif (
            sector_setting != "FMCG"
            and not manual_symbols.strip()
            and not selected_symbols
        ):

            st.error(
                "All Sectors অথবা Unverified Sector-এর জন্য "
                "এক বা একাধিক Stock নির্বাচন করুন। "
                "শুধু verified FMCG membership থেকে automatic "
                "sector scan করা যাবে।"
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
                        exchange=exchange,
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

    # ---------------------------------------------------------
    # 10. Persistent results
    # ---------------------------------------------------------

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
            "Verified NSE Stock নির্বাচন করুন অথবা FMCG-এর "
            "audited official membership ব্যবহার করুন। "
            "তারপর Run চাপুন।"
        )
