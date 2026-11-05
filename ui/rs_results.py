"""
TradeLab Pro - Relative Strength Results

Displays verified rankings and correctly ranked CSV exports.
"""

import streamlit as st
import pandas as pd


MAIN_SORT_COLUMN = "Excess Return (%)"
SECTOR_SORT_COLUMN = "Sector Excess Return (%)"

SECTOR_REQUIRED_COLUMNS = [
    "Stock",
    "Window",
    "Stock Return (%)",
    "Sector Return (%)",
    "Sector Excess Return (%)",
    "Common Sessions",
    "Start Date",
    "End Date",
]


def build_ranked_results(data, windows, sort_column):
    """Build independent ranking for every return window."""

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if sort_column not in df.columns or "Window" not in df.columns:
        raise ValueError(
            f"Required ranking columns missing: {sort_column}, Window"
        )

    ranked_parts = []

    for window_name in windows:
        view = df[df["Window"] == window_name].copy()

        if view.empty:
            continue

        view[sort_column] = pd.to_numeric(
            view[sort_column],
            errors="coerce",
        )

        view = view.dropna(subset=[sort_column])

        view = view.sort_values(
            sort_column,
            ascending=False,
            kind="stable",
        ).reset_index(drop=True)

        view.insert(0, "Rank", range(1, len(view) + 1))
        ranked_parts.append(view)

    if not ranked_parts:
        return pd.DataFrame()

    return pd.concat(ranked_parts, ignore_index=True)


def display_results(result):
    """Render Main Index and guarded Sector results with CSV exports."""

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
        try:
            ranked_main = build_ranked_results(
                main_results,
                windows,
                MAIN_SORT_COLUMN,
            )

            if ranked_main.empty:
                st.warning("Main Index Ranking তৈরি করা যায়নি।")

            else:
                for window_name in windows:
                    st.markdown(f"**{window_name} Ranking**")

                    view = ranked_main[
                        ranked_main["Window"] == window_name
                    ].copy()

                    if not view.empty:
                        st.dataframe(
                            view,
                            use_container_width=True,
                            hide_index=True,
                        )

                main_csv = ranked_main.to_csv(
                    index=False,
                ).encode("utf-8-sig")

                st.download_button(
                    "Download Main Index CSV",
                    data=main_csv,
                    file_name="tradelab_main_index_rs.csv",
                    mime="text/csv",
                    key="rs_main_csv",
                    on_click="ignore",
                )

        except ValueError as error:
            st.error(f"Main Ranking Error: {error}")

    else:
        st.warning(
            "Main Index-এর সঙ্গে তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
        )

    # -------------------------------------------------
    # Sector Comparison and Membership Guard
    # -------------------------------------------------

    st.divider()
    st.subheader("5. Stock vs Sector Index")

    sector_results = result.get("sector_results", [])

    sector_available = result.get(
        "sector_comparison_available",
        bool(sector_results),
    )

    sector_reason = result.get(
        "sector_comparison_reason",
        "",
    )

    if not sector_available:
        # Guard failed or sector data could not be retrieved.
        if sector_reason and not sector_reason.startswith(
            "All selected stocks"
        ):
            st.warning(
                "Sector Comparison বন্ধ রাখা হয়েছে। "
                "কারণ: " + sector_reason
            )
        else:
            if sector_reason:
                st.info(
                    "Sector Membership Guard: "
                    + sector_reason
                )

            st.info(
                "Guard যাচাইয়ের পরও Sector Comparison-এর জন্য "
                "তুলনাযোগ্য ফলাফল পাওয়া যায়নি। "
                "Main Index ফলাফল আলাদাভাবে উপলব্ধ থাকলে তা ব্যবহার করুন।"
            )

    elif not sector_results:
        st.info(
            "Sector Membership Guard পাস করেছে, "
            "কিন্তু Sector Comparison-এর ফলাফল পাওয়া যায়নি।"
        )

    else:
        sector_df = pd.DataFrame(sector_results)

        missing_columns = [
            column
            for column in SECTOR_REQUIRED_COLUMNS
            if column not in sector_df.columns
        ]

        if missing_columns:
            st.error(
                "Sector Results-এ প্রয়োজনীয় ডেটা পাওয়া যায়নি: "
                + ", ".join(missing_columns)
            )

        else:
            try:
                ranked_sector = build_ranked_results(
                    sector_results,
                    windows,
                    SECTOR_SORT_COLUMN,
                )

                if ranked_sector.empty:
                    st.warning(
                        "Sector Ranking তৈরি করা যায়নি।"
                    )

                else:
                    for window_name in windows:
                        st.markdown(
                            f"**{window_name} Sector Ranking**"
                        )

                        view = ranked_sector[
                            ranked_sector["Window"] == window_name
                        ].copy()

                        if not view.empty:
                            st.caption(
                                "Actual Comparison Period: "
                                f"{view['Start Date'].iloc[0]} to "
                                f"{view['End Date'].iloc[0]}"
                            )

                            st.dataframe(
                                view[["Rank"] + SECTOR_REQUIRED_COLUMNS],
                                use_container_width=True,
                                hide_index=True,
                            )

                    sector_csv = ranked_sector.to_csv(
                        index=False,
                    ).encode("utf-8-sig")

                    st.download_button(
                        "Download Sector Comparison CSV",
                        data=sector_csv,
                        file_name="tradelab_sector_rs.csv",
                        mime="text/csv",
                        key="rs_sector_csv",
                        on_click="ignore",
                    )

            except ValueError as error:
                st.error(f"Sector Ranking Error: {error}")

    # -------------------------------------------------
    # Data Retrieval Errors
    # -------------------------------------------------

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
