from io import StringIO

import pandas as pd

from ui import rs_results


def patch_streamlit_ui(monkeypatch, messages, downloads):
    """Replace Streamlit rendering calls with test recorders."""

    def record_message(name):
        def recorder(*args, **kwargs):
            messages.append((name, args, kwargs))
        return recorder

    for name in [
        "divider",
        "subheader",
        "write",
        "error",
        "warning",
        "info",
        "markdown",
        "dataframe",
        "caption",
    ]:
        monkeypatch.setattr(
            rs_results.st,
            name,
            record_message(name),
        )

    def record_download_button(label, **kwargs):
        downloads.append({
            "label": label,
            **kwargs,
        })
        return True

    monkeypatch.setattr(
        rs_results.st,
        "download_button",
        record_download_button,
    )


def sample_result():
    """Return a complete result payload for the UI test."""

    return {
        "sector": "FMCG",
        "selection_source": "Manual selection",
        "benchmark_name": "Nifty 50",
        "start_date": "2025-10-01",
        "end_date": "2026-10-31",
        "benchmark_error": None,
        "errors": [],
        "windows": ["1M"],
        "sector_comparison_available": True,
        "sector_comparison_reason": (
            "All selected stocks have configured sector membership."
        ),
        "main_results": [
            {
                "Stock": "MARICO",
                "Window": "1M",
                "Stock Return (%)": 12.0,
                "Main Index Return (%)": 5.0,
                "Excess Return (%)": 7.0,
                "Common Sessions": 20,
                "Start Date": "2026-10-01",
                "End Date": "2026-10-31",
            },
            {
                "Stock": "HINDUNILVR",
                "Window": "1M",
                "Stock Return (%)": 15.0,
                "Main Index Return (%)": 5.0,
                "Excess Return (%)": 10.0,
                "Common Sessions": 20,
                "Start Date": "2026-10-01",
                "End Date": "2026-10-31",
            },
        ],
        "sector_results": [
            {
                "Stock": "MARICO",
                "Window": "1M",
                "Stock Return (%)": 12.0,
                "Sector Return (%)": 4.0,
                "Sector Excess Return (%)": 8.0,
                "Common Sessions": 20,
                "Start Date": "2026-10-01",
                "End Date": "2026-10-31",
            },
            {
                "Stock": "HINDUNILVR",
                "Window": "1M",
                "Stock Return (%)": 15.0,
                "Sector Return (%)": 4.0,
                "Sector Excess Return (%)": 11.0,
                "Common Sessions": 20,
                "Start Date": "2026-10-01",
                "End Date": "2026-10-31",
            },
        ],
    }


def test_streamlit_ui_exports_main_and_sector_csv(monkeypatch):
    messages = []
    downloads = []

    patch_streamlit_ui(monkeypatch, messages, downloads)

    rs_results.display_results(sample_result())

    assert len(downloads) == 2

    main_download = next(
        item for item in downloads
        if item["label"] == "Download Main Index CSV"
    )

    sector_download = next(
        item for item in downloads
        if item["label"] == "Download Sector Comparison CSV"
    )

    assert main_download["file_name"] == "tradelab_main_index_rs.csv"
    assert sector_download["file_name"] == "tradelab_sector_rs.csv"

    assert main_download["mime"] == "text/csv"
    assert sector_download["mime"] == "text/csv"

    main_csv = pd.read_csv(
        StringIO(main_download["data"].decode("utf-8-sig"))
    )

    sector_csv = pd.read_csv(
        StringIO(sector_download["data"].decode("utf-8-sig"))
    )

    assert "Rank" in main_csv.columns
    assert "Rank" in sector_csv.columns

    assert main_csv["Stock"].tolist() == [
        "HINDUNILVR",
        "MARICO",
    ]

    assert main_csv["Rank"].tolist() == [1, 2]

    assert sector_csv["Stock"].tolist() == [
        "HINDUNILVR",
        "MARICO",
    ]

    assert sector_csv["Rank"].tolist() == [1, 2]


def test_sector_guard_failure_shows_exact_reason_and_hides_sector_csv(
    monkeypatch,
):
    messages = []
    downloads = []

    patch_streamlit_ui(monkeypatch, messages, downloads)

    result = sample_result()

    exact_reason = (
        "Sector membership is not verified for: MARICO"
    )

    result["sector_comparison_available"] = False
    result["sector_comparison_reason"] = exact_reason
    result["sector_results"] = []

    rs_results.display_results(result)

    displayed_text = " ".join(
        str(args)
        for name, args, kwargs in messages
        if name in {"info", "warning", "error"}
    )

    assert exact_reason in displayed_text

    download_labels = [
        item["label"]
        for item in downloads
    ]

    assert "Download Main Index CSV" in download_labels
    assert "Download Sector Comparison CSV" not in download_labels


def test_sector_guard_pass_but_no_results_shows_no_data_message(
    monkeypatch,
):
    messages = []
    downloads = []

    patch_streamlit_ui(monkeypatch, messages, downloads)

    result = sample_result()
    result["sector_comparison_available"] = False
    result["sector_results"] = []

    rs_results.display_results(result)

    displayed_text = " ".join(
        str(args)
        for name, args, kwargs in messages
        if name == "info"
    )

    assert "Membership Guard" in displayed_text
    assert "তুলনাযোগ্য ফলাফল পাওয়া যায়নি" in displayed_text

