"""
TradeLab Pro - Shared Data Settings

Only verified and configured market-data options are exposed.
Settings are shared with the Relative Strength Scanner.
"""

import streamlit as st

from data.benchmark_mapping import (
    get_main_benchmarks,
    get_available_sector_mappings,
)


ACTIVE_DATA_SOURCE = "NSE Primary + Yahoo Secondary"

EXCHANGE_OPTIONS = [
    "NSE",
    "BSE",
    "Both",
]

MARKET_CAP_OPTIONS = [
    "All Market Caps",
    "Large Cap",
    "Mid Cap",
    "Small Cap",
]


def get_verified_sectors():
    """Return All Sectors plus only verified sector mappings."""

    mappings = get_available_sector_mappings()

    return [
        "All Sectors",
        *sorted(mappings.keys()),
    ]


# Keep this public name for existing UI imports.
SECTORS = get_verified_sectors()


def _initialize_settings():
    """Initialize shared application settings safely."""

    benchmarks = get_main_benchmarks()

    if not benchmarks:
        raise ValueError(
            "No verified Main Benchmark mapping is configured."
        )

    default_benchmark = next(iter(benchmarks))

    # Read legacy setting BEFORE inserting new defaults.
    legacy_benchmark = st.session_state.get(
        "settings_benchmark",
        default_benchmark,
    )

    if legacy_benchmark not in benchmarks:
        legacy_benchmark = default_benchmark

    defaults = {
        "data_source": ACTIVE_DATA_SOURCE,
        "settings_exchange": "NSE",
        "settings_start_date": None,
        "settings_end_date": None,
        "settings_benchmark": legacy_benchmark,
        "settings_main_benchmarks": [legacy_benchmark],
        "settings_sector": "All Sectors",
        "settings_market_cap": "All Market Caps",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Migrate the old Yahoo-only label to the actual adapter.
    if st.session_state["data_source"] == "Yahoo Finance":
        st.session_state["data_source"] = ACTIVE_DATA_SOURCE

    # Validate saved benchmark selections against verified mappings.
    selected = st.session_state.get(
        "settings_main_benchmarks",
        [],
    )

    if not isinstance(selected, (list, tuple)):
        selected = []

    selected = [
        name
        for name in selected
        if name in benchmarks
    ]

    if not selected:
        legacy = st.session_state.get(
            "settings_benchmark",
            default_benchmark,
        )

        selected = [
            legacy if legacy in benchmarks else default_benchmark
        ]

    st.session_state["settings_main_benchmarks"] = selected

    # Preserve the legacy single-benchmark setting.
    st.session_state["settings_benchmark"] = selected[0]

    # Never retain an unverified sector selection.
    if st.session_state["settings_sector"] not in SECTORS:
        st.session_state["settings_sector"] = "All Sectors"

    if st.session_state["settings_exchange"] not in EXCHANGE_OPTIONS:
        st.session_state["settings_exchange"] = "NSE"

    if st.session_state["settings_market_cap"] not in MARKET_CAP_OPTIONS:
        st.session_state["settings_market_cap"] = "All Market Caps"


def render_settings_page():
    """Render verified market-data and scanner preferences."""

    _initialize_settings()

    benchmarks = get_main_benchmarks()

    st.header("Settings (Data)")
    st.caption(
        "TradeLab Pro · Shared Market Data Configuration"
    )

    # ---------------------------------------------------------
    # 1. Data Source
    # ---------------------------------------------------------

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
        "সংযুক্ত নয়। এগুলোকে Active Source হিসেবে দেখানো হচ্ছে।"
    )

    # ---------------------------------------------------------
    # 2. Exchange
    # ---------------------------------------------------------

    st.divider()
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

    elif exchange == "BSE":

        st.warning(
            "BSE Scanner নিষ্ক্রিয়। Official BSE Universe এবং "
            "validated BSE Data Adapter সম্পূর্ণ না হওয়া পর্যন্ত "
            "BSE Analysis চালানো যাবে না।"
        )

    else:

        st.warning(
            "Both Exchange mode এখনো নিষ্ক্রিয়। "
            "NSE এবং BSE-এর পৃথক verified data pipeline "
            "সম্পূর্ণ না হওয়া পর্যন্ত এটি ব্যবহার করা যাবে না।"
        )

    # ---------------------------------------------------------
    # 3. Historical Date Range
    # ---------------------------------------------------------

    st.divider()
    st.subheader("3. Historical Date Range")

    col1, col2 = st.columns(2)

    with col1:

        start_date = st.date_input(
            "Start Date",
            value=st.session_state["settings_start_date"],
            key="settings_start_date",
            help=(
                "এই Date Range Relative Strength Scanner ব্যবহার করবে।"
            ),
        )

    with col2:

        end_date = st.date_input(
            "End Date",
            value=st.session_state["settings_end_date"],
            key="settings_end_date",
            help=(
                "এই Date Range Relative Strength Scanner ব্যবহার করবে।"
            ),
        )

    valid_dates = True

    if start_date and end_date and start_date >= end_date:

        st.error(
            "Start Date অবশ্যই End Date-এর আগের হতে হবে।"
        )

        valid_dates = False

    elif bool(start_date) != bool(end_date):

        st.warning(
            "সম্পূর্ণ Date Range দিতে Start Date এবং End Date "
            "দুটিই নির্বাচন করুন।"
        )

        valid_dates = False

    # ---------------------------------------------------------
    # 4. Main Benchmark Selection
    # ---------------------------------------------------------

    st.divider()
    st.subheader("4. Main Benchmark")

    benchmark_names = list(benchmarks.keys())

    selected_benchmarks = st.multiselect(
        "Select Main Benchmark Indices",
        options=benchmark_names,
        default=st.session_state["settings_main_benchmarks"],
        key="settings_main_benchmarks",
        help=(
            "একাধিক Main Benchmark নির্বাচন করা যাবে। "
            "প্রতিটি Benchmark-এর বিরুদ্ধে Stock Return এবং "
            "Excess Return আলাদাভাবে গণনা করা হবে।"
        ),
    )

    if not selected_benchmarks:

        st.error(
            "কমপক্ষে একটি Main Benchmark নির্বাচন করুন।"
        )

        valid_dates = False

    else:

        # Keep the old single-benchmark key synchronized.
        st.session_state["settings_benchmark"] = (
            selected_benchmarks[0]
        )

        st.caption("Verified Benchmark Mappings:")

        for benchmark_name in selected_benchmarks:

            st.write(
                f"- **{benchmark_name}:** "
                f"`{benchmarks[benchmark_name]}`"
            )

    # ---------------------------------------------------------
    # 5. Verified Sector Selection
    # ---------------------------------------------------------

    st.divider()
    st.subheader("5. Sector")

    verified_sectors = get_verified_sectors()

    sector = st.selectbox(
        "Select Sector",
        verified_sectors,
        key="settings_sector",
        help=(
            "শুধু configured verified Sector Mapping দেখানো হবে।"
        ),
    )

    sector_mappings = get_available_sector_mappings()

    if sector == "All Sectors":

        st.info(
            "All Sectors নির্বাচন করলে Scanner-এর জন্য "
            "Stock Universe থেকে Stock নির্বাচন করতে হবে। "
            "Sector Index Comparison চালানো হবে না।"
        )

    elif sector in sector_mappings:

        st.success(
            f"Verified Sector Benchmark: "
            f"{sector} ({sector_mappings[sector]})"
        )

        st.caption(
            "Sector Comparison-এর আগে official constituent "
            "membership audit সম্পন্ন হতে হবে।"
        )

    else:

        st.error(
            "Unverified Sector Selection শনাক্ত হয়েছে। "
            "এই Sector ব্যবহার করা যাবে না।"
        )

    # ---------------------------------------------------------
    # 6. Market Capitalization
    # ---------------------------------------------------------

    st.divider()
    st.subheader("6. Market Capitalization")

    market_cap = st.selectbox(
        "Market Cap Filter",
        MARKET_CAP_OPTIONS,
        key="settings_market_cap",
        help=(
            "Relative Strength Scanner একই Market Cap setting ব্যবহার করবে।"
        ),
    )

    st.caption(
        "Classification uses the latest available official "
        "AMFI half-yearly data. Only verified ISIN and NSE "
        "Symbol matches are eligible."
    )

    # ---------------------------------------------------------
    # 7. Current Configuration
    # ---------------------------------------------------------

    st.divider()
    st.subheader("Current Configuration")

    st.write(
        f"**Data Source:** {ACTIVE_DATA_SOURCE}"
    )

    st.write(
        f"**Exchange:** {exchange}"
    )

    st.write(
        f"**Start Date:** {start_date or 'Not selected'}"
    )

    st.write(
        f"**End Date:** {end_date or 'Not selected'}"
    )

    st.write(
        "**Main Benchmarks:** "
        + (
            ", ".join(selected_benchmarks)
            if selected_benchmarks
            else "None selected"
        )
    )

    st.write(
        f"**Sector:** {sector}"
    )

    st.write(
        f"**Market Capitalization:** {market_cap}"
    )

    # ---------------------------------------------------------
    # 8. Validation
    # ---------------------------------------------------------

    if valid_dates:

        st.success(
            "Settings values are valid and stored in the "
            "Streamlit session."
        )

    else:

        st.warning(
            "Date configuration অথবা Benchmark Selection "
            "অসম্পূর্ণ বা invalid।"
        )

    st.caption(
        "এই Settings একই Streamlit session-এ Relative Strength "
        "Scanner-এর সঙ্গে shared থাকবে। BSE এবং Both এখনো "
        "fail-closed অবস্থায় থাকবে।"
    )
    
