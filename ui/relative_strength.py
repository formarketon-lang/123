import streamlit as st
import pandas as pd
from datetime import date, timedelta

from data.yahoo_adapter import fetch_yahoo_history
from rs_engine import compare_on_common_dates


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

SECTOR_UNIVERSE = {
    "FMCG": ["HINDUNILVR"],
}

MAIN_BENCHMARKS = {
    "Nifty 50": "^NSEI",
    "Nifty Next 50": "^NSMIDCP",
    "Nifty 100": "^CNX100",
    "Nifty 200": "^CNX200",
    "Nifty 500": "^CRSLDX",
}

# Sector index symbols must be verified before activation.
SECTOR_BENCHMARKS = {}


# ---------------------------------------------------------
# MARKET DATA
# ---------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def get_market_data(symbol, start_date, end_date, exchange):
    return fetch_yahoo_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange=exchange,
    )


def resolve_symbols(sector, manual_symbols):

    if manual_symbols.strip():

        symbols = [
            item.strip().upper()
            for item in manual_symbols.replace("\n", ",").split(",")
            if item.strip()
        ]

        return list(dict.fromkeys(symbols)), "Manual selection"

    if sector in SECTOR_UNIVERSE:
        return SECTOR_UNIVERSE[sector], "Configured starter universe"

    raise ValueError(
        "এই Sector-এর Stock Universe এখনো তৈরি হয়নি। "
        "Manual Stock Symbol লিখুন।"
    )


def build_windows(start_date, end_date, custom_windows):

    windows = {
        "Selected Period": (start_date, end_date),
    }

    if custom_windows:

        for item in custom_windows:

            if item == "1M":
                days = 30
            elif item == "3M":
                days = 90
            elif item == "6M":
                days = 180
            elif item == "1Y":
                days = 365
            else:
                continue

            window_start = end_date - timedelta(days=days)

            if window_start >= start_date:
                windows[item] = (window_start, end_date)

    return windows


# ---------------------------------------------------------
# MAIN PAGE
# ---------------------------------------------------------

def render_relative_strength_page():

    st.header("Relative Strength Scanner")

    st.caption(
        "TradeLab Pro · NSE/BSE Cash Market · "
        "Stock vs Sector vs Main Index"
    )

    # -----------------------------------------------------
    # 1. STOCK SELECTION
    # -----------------------------------------------------

    st.subheader("1. Stock Selection")

    sectors = [
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

    sector = st.selectbox(
        "Select Sector",
        sectors,
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

    # -----------------------------------------------------
    # 2. BENCHMARK SELECTION
    # -----------------------------------------------------

    st.divider()
    st.subheader("2. Benchmark Selection")

    benchmark_name = st.selectbox(
        "Main Benchmark Index",
        list(MAIN_BENCHMARKS.keys()),
        key="rs_main_benchmark",
    )

    sector_benchmark_name = None
    sector_benchmark_symbol = None

    if sector in SECTOR_BENCHMARKS:

        sector_benchmark_name = sector
        sector_benchmark_symbol = SECTOR_BENCHMARKS[sector]

        st.success(
            f"Sector Benchmark: {sector_benchmark_name}"
        )

    else:

        st.warning(
            "এই Sector-এর verified Index Mapping এখনো যুক্ত হয়নি। "
            "Sector Comparison বর্তমানে unavailable।"
        )

    # -----------------------------------------------------
    # 3. DATE RANGE AND WINDOWS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 4. RUN SCANNER
    # -----------------------------------------------------

    st.divider()

    run_button = st.button(
        "Run Relative Strength Scanner",
        type="primary",
        use_container_width=True,
    )

    if not run_button:

        st.info(
            "Selection সম্পূর্ণ করে Run চাপুন।"
        )

        return

    if start_date >= end_date:

        st.error(
            "Start Date অবশ্যই End Date-এর আগের হতে হবে।"
        )

        return

    try:

        symbols, selection_source = resolve_symbols(
            sector,
            manual_symbols,
        )

    except ValueError as error:

        st.error(str(error))
        return

    windows = build_windows(
        start_date,
        end_date,
        custom_windows,
    )

    benchmark_symbol = MAIN_BENCHMARKS[benchmark_name]

    fetch_start = start_date - timedelta(days=10)

    main_results = []
    sector_results = []
    errors = []

    # -----------------------------------------------------
    # 5. FETCH DATA AND COMPARE
    # -----------------------------------------------------

    with st.spinner(
        "Market Data সংগ্রহ এবং Relative Strength বিশ্লেষণ চলছে..."
    ):

        try:

            main_benchmark_data = get_market_data(
                benchmark_symbol,
                fetch_start,
                end_date,
                "NSE",
            )

        except Exception as error:

            st.error(
                f"Main Benchmark Data পাওয়া যায়নি: {error}"
            )

            return

        sector_data = None

        if sector_benchmark_symbol:

            try:

                sector_data = get_market_data(
                    sector_benchmark_symbol,
                    fetch_start,
                    end_date,
                    "NSE",
                )

            except Exception as error:

                errors.append({
                    "Stock": "SECTOR INDEX",
                    "Reason": str(error),
                })

        for symbol in symbols:

            try:

                stock_data = get_market_data(
                    symbol,
                    fetch_start,
                    end_date,
                    exchange,
                )

                for window_name, dates in windows.items():

                    window_start, window_end = dates

                    # Stock vs Main Benchmark
                    main_comparison = compare_on_common_dates(
                        stock_data=stock_data,
                        benchmark_data=main_benchmark_data,
                        start_date=window_start,
                        end_date=window_end,
                    )

                    main_results.append({

                        "Stock": symbol,
                        "Window": window_name,

                        "Stock Return (%)": round(
                            main_comparison["stock_return_pct"], 2
                        ),

                        "Main Index Return (%)": round(
                            main_comparison["benchmark_return_pct"], 2
                        ),

                        "Excess Return (%)": round(
                            main_comparison["stock_vs_benchmark_pct"], 2
                        ),

                        "Common Sessions": (
                            main_comparison["common_trading_sessions"]
                        ),

                        "Start Date": main_comparison["start_date"],
                        "End Date": main_comparison["end_date"],

                    })

                    # Stock vs Sector Benchmark
                    if sector_data is not None:

                        sector_comparison = compare_on_common_dates(
                            stock_data=stock_data,
                            benchmark_data=sector_data,
                            start_date=window_start,
                            end_date=window_end,
                        )

                        sector_results.append({

                            "Stock": symbol,
                            "Window": window_name,

                            "Stock Return (%)": round(
                                sector_comparison["stock_return_pct"], 2
                            ),

                            "Sector Return (%)": round(
                                sector_comparison["benchmark_return_pct"], 2
                            ),

                            "Sector Excess Return (%)": round(
                                sector_comparison["stock_vs_benchmark_pct"], 2
                            ),

                            "Common Sessions": (
                                sector_comparison["common_trading_sessions"]
                            ),

                        })

            except Exception as error:

                errors.append({
                    "Stock": symbol,
                    "Reason": str(error),
                })

    # -----------------------------------------------------
    # 6. MAIN INDEX RESULTS
    # -----------------------------------------------------

    st.divider()
    st.subheader("4. Stock vs Main Index")

    st.write(
        f"**Sector:** {sector}  \n"
        f"**Selection:** {selection_source}  \n"
        f"**Main Benchmark:** {benchmark_name}"
    )

    if main_results:

        main_df = pd.DataFrame(main_results)

        for window_name in windows:

            st.markdown(f"**{window_name} Ranking**")

            view = main_df[
                main_df["Window"] == window_name
            ].copy()

            view = view.sort_values(
                "Excess Return (%)",
                ascending=False,
            ).reset_index(drop=True)

            view.insert(
                0,
                "Rank",
                range(1, len(view) + 1),
            )

            st.dataframe(
                view,
                use_container_width=True,
                hide_index=True,
            )

        main_csv = main_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Download Main Index CSV",
            data=main_csv,
            file_name="tradelab_main_index_rs.csv",
            mime="text/csv",
        )

    else:

        st.warning(
            "Main Index-এর সঙ্গে তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
        )

    # -----------------------------------------------------
    # 7. SECTOR RESULTS
    # -----------------------------------------------------

    st.divider()
    st.subheader("5. Stock vs Sector Index")

    if sector_results:

        sector_df = pd.DataFrame(sector_results)

        for window_name in windows:

            st.markdown(f"**{window_name} Sector Ranking**")

            view = sector_df[
                sector_df["Window"] == window_name
            ].copy()

            view = view.sort_values(
                "Sector Excess Return (%)",
                ascending=False,
            ).reset_index(drop=True)

            view.insert(
                0,
                "Rank",
                range(1, len(view) + 1),
            )

            st.dataframe(
                view,
                use_container_width=True,
                hide_index=True,
            )

        sector_csv = sector_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Download Sector Comparison CSV",
            data=sector_csv,
            file_name="tradelab_sector_rs.csv",
            mime="text/csv",
        )

    else:

        st.info(
            "Verified Sector Index Mapping যুক্ত হলে "
            "এই বিভাগে Sector Comparison দেখা যাবে।"
        )

    # -----------------------------------------------------
    # 8. ERRORS
    # -----------------------------------------------------

    if errors:

        st.divider()
        st.subheader("6. Data Retrieval Errors")

        st.dataframe(
            pd.DataFrame(errors),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Excess Return = Stock Return − Benchmark Return. "
        "এটি percentage-point difference, ভবিষ্যৎ Return-এর পূর্বাভাস নয়।"
    )
    
