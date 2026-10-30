
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from data.yahoo_adapter import fetch_yahoo_history
from rs_engine import compare_stock_with_benchmark


# আপাতত কনফিগার করা Starter Universe
SECTOR_UNIVERSE = {
    "FMCG": ["HINDUNILVR"],
}

BENCHMARKS = {
    "Nifty 50": "^NSEI",
}


@st.cache_data(ttl=900, show_spinner=False)
def get_market_data(symbol, start_date, end_date, exchange):
    """Yahoo Finance থেকে Historical OHLCV ডেটা সংগ্রহ।"""
    return fetch_yahoo_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        interval="1d",
        exchange=exchange,
    )


def resolve_symbols(sector, manual_symbols):
    """Manual symbols অথবা configured sector universe ফেরত দেয়।"""

    if manual_symbols:
        symbols = [
            item.strip().upper()
            for item in manual_symbols.replace("\n", ",").split(",")
            if item.strip()
        ]
        return list(dict.fromkeys(symbols)), "Manual selection"

    if sector in SECTOR_UNIVERSE:
        return SECTOR_UNIVERSE[sector], "Configured starter universe"

    raise ValueError(
        "এই সেক্টরের জন্য এখনো Stock Universe তৈরি হয়নি। "
        "Stock Symbol ঘরে এক বা একাধিক Symbol লিখুন।"
    )


def render_relative_strength_page():

    st.header("Relative Strength")
    st.caption(
        "NSE/BSE Cash Market · Live Historical Data · "
        "Stock vs Benchmark"
    )

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
        "Sector",
        sectors,
        index=0,
        key="rs_sector",
    )

    manual_symbols = st.text_area(
        "Search Stock Symbol(s) — Optional",
        placeholder="উদাহরণ: HINDUNILVR, RELIANCE, INFY",
        key="rs_stock_search",
        help="একাধিক Symbol কমা অথবা নতুন লাইনে লিখুন।",
    )

    exchange = st.selectbox(
        "Exchange",
        ["NSE", "BSE"],
        index=0,
        key="rs_exchange",
    )

    if not manual_symbols.strip() and sector == "FMCG":
        st.info(
            "FMCG Starter Universe: HINDUNILVR। "
            "সম্পূর্ণ FMCG Universe এখনো যুক্ত হয়নি।"
        )

    st.divider()
    st.subheader("2. Benchmark & Date Range")

    benchmark_name = st.selectbox(
        "Benchmark Index",
        list(BENCHMARKS.keys()),
        index=0,
        key="rs_benchmark",
    )

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "Start Date",
            value=date.today() - timedelta(days=120),
            key="rs_start_date",
        )

    with col2:
        end_date = st.date_input(
            "End Date",
            value=date.today(),
            key="rs_end_date",
        )

    st.caption(
        "বর্তমান Phase-এ Daily timeframe ব্যবহার করা হচ্ছে। "
        "Intraday ও অতিরিক্ত Benchmark পরবর্তী ধাপে যুক্ত হবে।"
    )

    st.divider()

    run_button = st.button(
        "Run Live Relative Strength Scanner",
        type="primary",
        use_container_width=True,
        key="rs_run",
    )

    if not run_button:
        st.info(
            "Stock নির্বাচন করে তারিখ ও Benchmark নির্ধারণ করুন, "
            "তারপর Run চাপুন।"
        )
        return

    if start_date >= end_date:
        st.error("Start Date অবশ্যই End Date-এর আগের হতে হবে।")
        return

    try:
        symbols, selection_source = resolve_symbols(
            sector,
            manual_symbols,
        )
    except ValueError as error:
        st.error(str(error))
        return

    benchmark_symbol = BENCHMARKS[benchmark_name]

    # Start Date-এর আগের কয়েক দিনও নেওয়া হচ্ছে,
    # যাতে ছুটির দিনের জন্য আগের Trading Close পাওয়া যায়।
    fetch_start = start_date - timedelta(days=10)

    results = []
    errors = []

    with st.spinner(
        "Yahoo Finance থেকে বাস্তব Market Data সংগ্রহ করা হচ্ছে..."
    ):

        try:
            benchmark_data = get_market_data(
                benchmark_symbol,
                fetch_start,
                end_date,
                "NSE",
            )
        except Exception as error:
            st.error(
                f"{benchmark_name} Benchmark Data পাওয়া যায়নি: {error}"
            )
            return

        for symbol in symbols:

            try:
                stock_data = get_market_data(
                    symbol,
                    fetch_start,
                    end_date,
                    exchange,
                )

                comparison = compare_stock_with_benchmark(
                    stock_data,
                    benchmark_data,
                    start_date,
                    end_date,
                )

                results.append({
                    "Stock": symbol,
                    "Exchange": exchange,
                    "Stock Return (%)": round(
                        comparison["stock_return_pct"], 2
                    ),
                    "Benchmark Return (%)": round(
                        comparison["benchmark_return_pct"], 2
                    ),
                    "Excess Return (%)": round(
                        comparison["relative_performance_pct"], 2
                    ),
                    "Data Rows": len(stock_data),
                    "Last Data Date": (
                        pd.to_datetime(stock_data["Date"].max())
                        .strftime("%Y-%m-%d")
                    ),
                })

            except Exception as error:
                errors.append({
                    "Stock": symbol,
                    "Reason": str(error),
                })

    st.divider()
    st.subheader("3. Scanner Results")

    st.write(
        f"**Selection:** {selection_source}  \n"
        f"**Benchmark:** {benchmark_name}  \n"
        f"**Period:** {start_date} to {end_date}"
    )

    if results:

        result_df = pd.DataFrame(results)

        result_df = result_df.sort_values(
            "Excess Return (%)",
            ascending=False,
        ).reset_index(drop=True)

        result_df.insert(
            0,
            "Rank",
            range(1, len(result_df) + 1),
        )

        st.success(
            f"{len(result_df)}টি Stock-এর বাস্তব Historical Data "
            "পাওয়া গেছে।"
        )

        st.dataframe(
            result_df,
            use_container_width=True,
            hide_index=True,
        )

        best = result_df.iloc[0]

        st.subheader("Relative Strength Summary")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Stock Return",
            f"{best['Stock Return (%)']:.2f}%",
        )

        c2.metric(
            "Benchmark Return",
            f"{best['Benchmark Return (%)']:.2f}%",
        )

        c3.metric(
            "Excess Return",
            f"{best['Excess Return (%)']:.2f}%",
        )

        csv_data = result_df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Download CSV Results",
            data=csv_data,
            file_name="tradelab_relative_strength.csv",
            mime="text/csv",
            use_container_width=True,
        )

        st.caption(
            "Positive Excess Return = Benchmark-এর তুলনায় "
            "তুলনামূলক ভালো Performance। "
            "Negative Excess Return = Benchmark-এর তুলনায় "
            "Underperformance। এটি ভবিষ্যৎ Return-এর পূর্বাভাস নয়।"
        )

    else:
        st.warning(
            "কোনো Stock-এর জন্য তুলনাযোগ্য Data পাওয়া যায়নি।"
        )

    if errors:
        st.subheader("Data Retrieval Errors")
        st.dataframe(
            pd.DataFrame(errors),
            use_container_width=True,
            hide_index=True,
        )
