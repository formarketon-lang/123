"""
TradeLab Pro - Relative Strength Results

Displays rankings, comparison tables and CSV downloads.
"""

import streamlit as st
import pandas as pd


def display_results(result):

    st.divider()
    st.subheader("4. Stock vs Main Index")

    st.write(
        f"**Sector:** {result['sector']}  \n"
        f"**Selection:** {result['selection_source']}  \n"
        f"**Main Benchmark:** {result['benchmark_name']}  \n"
        f"**Last Run Period:** {result['start_date']} to "
        f"{result['end_date']}"
    )

    if result["benchmark_error"]:
        st.error(
            "Main Benchmark Data পাওয়া যায়নি: "
            + result["benchmark_error"]
        )

    main_results = result["main_results"]
    windows = result["windows"]

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

            view.insert(0, "Rank", range(1, len(view) + 1))

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
            key="rs_main_csv",
            on_click="ignore",
        )

    else:
        st.warning(
            "Main Index-এর সঙ্গে তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
        )

    # Sector results
    st.divider()
    st.subheader("5. Stock vs Sector Index")

    sector_results = result["sector_results"]

    if sector_results:

        sector_df = pd.DataFrame(sector_results)

        for window_name in windows:

            st.markdown(
                f"**{window_name} Sector Ranking**"
            )

            view = sector_df[
                sector_df["Window"] == window_name
            ].copy()

            view = view.sort_values(
                "Sector Excess Return (%)",
                ascending=False,
            ).reset_index(drop=True)

            view.insert(0, "Rank", range(1, len(view) + 1))

            # Display comparison period
            if "Start Date" in view.columns and "End Date" in view.columns:

                st.caption(
                    f"Comparison Period: "
                    f"{view['Start Date'].iloc[0]} to "
                    f"{view['End Date'].iloc[0]}"
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
            key="rs_sector_csv",
            on_click="ignore",
        )

    else:
        st.info(
            "Verified Sector Index Mapping যুক্ত হলে "
            "এই বিভাগে Sector Comparison দেখা যাবে।"
        )

    # Errors
    if result["errors"]:

        st.divider()
        st.subheader("6. Data Retrieval Errors")

        st.dataframe(
            pd.DataFrame(result["errors"]),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Excess Return = Stock Return − Benchmark Return. "
        "এটি percentage-point difference, ভবিষ্যৎ Return-এর পূর্বাভাস নয়।"
    )
    
