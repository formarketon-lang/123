
"""
TradeLab Pro - Relative Strength Results

Displays independent rankings for each Main Benchmark and
return window. Sector comparison remains separately guarded.
CSV exports preserve Benchmark identity.
"""

import pandas as pd
import streamlit as st


MAIN_SORT_COLUMN = "Excess Return (%)"
SECTOR_SORT_COLUMN = "Sector Excess Return (%)"

MAIN_REQUIRED_COLUMNS = [
    "Benchmark",
    "Stock",
    "Window",
    "Stock Return (%)",
    "Main Index Return (%)",
    "Excess Return (%)",
    "Common Sessions",
    "Start Date",
    "End Date",
]

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
    """Build independent ranking for every benchmark and window."""
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    if sort_column not in df.columns or "Window" not in df.columns:
        raise ValueError(
            f"Required ranking columns missing: {sort_column}, Window"
        )

    # Backward compatibility for historical single-benchmark results.
    if sort_column == MAIN_SORT_COLUMN and "Benchmark" not in df.columns:
        df["Benchmark"] = "Main Benchmark"

    group_columns = []
    if "Benchmark" in df.columns:
        group_columns.append("Benchmark")
    group_columns.append("Window")

    ranked_parts = []

    group_values = df[group_columns].drop_duplicates().to_dict("records")

    for group in group_values:
        mask = pd.Series(True, index=df.index)
        for column, value in group.items():
            mask &= df[column] == value

        view = df.loc[mask].copy()
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

        if view.empty:
            continue

        view.insert(0, "Rank", range(1, len(view) + 1))
        ranked_parts.append(view)

    if not ranked_parts:
        return pd.DataFrame()

    return pd.concat(ranked_parts, ignore_index=True)


def _display_main_results(result):
    """Display Main Index results grouped by benchmark and window."""
    main_results = result.get("main_results", [])
    windows = result.get("windows", [])

    if not main_results:
        st.warning(
            "Main Index-এর সঙ্গে তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
        )
        return

    try:
        ranked = build_ranked_results(
            main_results,
            windows,
            MAIN_SORT_COLUMN,
        )

        if ranked.empty:
            st.warning("Main Index Ranking তৈরি করা যায়নি।")
            return

        missing = [
            column for column in MAIN_REQUIRED_COLUMNS
            if column not in ranked.columns
        ]
        if missing:
            st.error(
                "Main Results-এ প্রয়োজনীয় ডেটা পাওয়া যায়নি: "
                + ", ".join(missing)
            )
            return

        benchmark_names = (
            result.get("benchmark_names")
            or ranked["Benchmark"].drop_duplicates().tolist()
        )

        for benchmark in benchmark_names:
            st.markdown(f"### {benchmark} Ranking")

            benchmark_view = ranked[
                ranked["Benchmark"] == benchmark
            ]

            for window_name in windows:
                view = benchmark_view[
                    benchmark_view["Window"] == window_name
                ].copy()

                if view.empty:
                    continue

                st.markdown(f"**{window_name}**")
                st.dataframe(
                    view,
                    use_container_width=True,
                    hide_index=True,
                )

        csv_data = ranked.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "Download All Main Benchmark Rankings CSV",
            data=csv_data,
            file_name="tradelab_multi_benchmark_rs.csv",
            mime="text/csv",
            key="rs_multi_main_csv",
            on_click="ignore",
        )

    except ValueError as error:
        st.error(f"Main Ranking Error: {error}")


def _display_sector_results(result):
    """Display guarded Sector Comparison and its CSV export."""
    sector_results = result.get("sector_results", [])
    sector_available = result.get(
        "sector_comparison_available",
        bool(sector_results),
    )
    sector_reason = result.get("sector_comparison_reason", "")

    if not sector_available:
        if sector_reason:
            st.warning(
                "Sector Comparison বন্ধ রাখা হয়েছে। কারণ: "
                + sector_reason
            )
        else:
            st.info(
                "Sector Comparison-এর জন্য verified এবং "
                "তুলনাযোগ্য ফলাফল পাওয়া যায়নি।"
            )
        return

    if not sector_results:
        st.info(
            "Sector Membership Guard পাস করেছে, কিন্তু "
            "Sector Comparison-এর ফলাফল পাওয়া যায়নি।"
        )
        return

    sector_df = pd.DataFrame(sector_results)
    missing = [
        column for column in SECTOR_REQUIRED_COLUMNS
        if column not in sector_df.columns
    ]

    if missing:
        st.error(
            "Sector Results-এ প্রয়োজনীয় ডেটা পাওয়া যায়নি: "
            + ", ".join(missing)
        )
        return

    try:
        ranked = build_ranked_results(
            sector_results,
            result.get("windows", []),
            SECTOR_SORT_COLUMN,
        )

        if ranked.empty:
            st.warning("Sector Ranking তৈরি করা যায়নি।")
            return

        for window_name in result.get("windows", []):
            view = ranked[
                ranked["Window"] == window_name
            ].copy()

            if view.empty:
                continue

            st.markdown(f"**{window_name} Sector Ranking**")
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

        csv_data = ranked.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "Download Sector Comparison CSV",
            data=csv_data,
            file_name="tradelab_sector_rs.csv",
            mime="text/csv",
            key="rs_sector_csv",
            on_click="ignore",
        )

    except ValueError as error:
        st.error(f"Sector Ranking Error: {error}")


def display_results(result):
    """Render Main Benchmark and guarded Sector results."""
    st.divider()
    st.subheader("Stock vs Main Benchmarks")

    benchmark_names = (
        result.get("benchmark_names")
        or [result.get("benchmark_name", "Main Benchmark")]
    )

    st.write(
        f"**Sector:** {result.get('sector')}  \n"
        f"**Selection:** {result.get('selection_source')}  \n"
        f"**Main Benchmarks:** {', '.join(benchmark_names)}  \n"
        f"**Last Run Period:** {result.get('start_date')} to "
        f"{result.get('end_date')}"
    )

    benchmark_errors = result.get("benchmark_errors", {})
    if benchmark_errors:
        st.error("এক বা একাধিক Main Benchmark-এর Data পাওয়া যায়নি।")
        st.dataframe(
            pd.DataFrame([
                {"Benchmark": name, "Reason": reason}
                for name, reason in benchmark_errors.items()
            ]),
            use_container_width=True,
            hide_index=True,
        )
    elif result.get("benchmark_error"):
        st.error(
            "Main Benchmark Data পাওয়া যায়নি: "
            + str(result["benchmark_error"])
        )

    _display_main_results(result)

    st.divider()
    st.subheader("Stock vs Sector Index")
    _display_sector_results(result)

    errors = result.get("errors", [])
    if errors:
        st.divider()
        st.subheader("Data Retrieval / Comparison Errors")
        st.dataframe(
            pd.DataFrame(errors),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Excess Return = Stock Return − Benchmark Return. "
        "এটি percentage-point difference, ভবিষ্যৎ Return-এর পূর্বাভাস নয়।"
    )
