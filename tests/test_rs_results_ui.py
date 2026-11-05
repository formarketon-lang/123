
from io import StringIO

import pandas as pd

from ui import rs_results


def _mock_streamlit(monkeypatch):
    """Capture Streamlit output and download buttons for UI tests."""
    displayed_text = []
    downloads = []

    def capture_text(*args, **kwargs):
        displayed_text.extend(str(arg) for arg in args)

    def capture_download(label, **kwargs):
        downloads.append({
            "label": label,
            "data": kwargs.get("data"),
            "file_name": kwargs.get("file_name"),
            "mime": kwargs.get("mime"),
        })
        return True

    render_methods = [
        "divider",
        "subheader",
        "write",
        "error",
        "warning",
        "info",
        "markdown",
        "dataframe",
        "caption",
    ]

    for method in render_methods:
        monkeypatch.setattr(
            rs_results.st,
            method,
            capture_text,
        )

    monkeypatch.setattr(
        rs_results.st,
        "download_button",
        capture_download,
    )

    return displayed_text, downloads


def _base_result():
    return {
        "sector": "FMCG",
        "selection_source": "Manual",
        "benchmark_name": "Nifty 50",
        "start_date": "2025-10-31",
        "end_date": "2026-10-30",
        "benchmark_error": None,
        "windows": ["1M"],
        "errors": [],
        "main_results": [
            {
                "Stock": "AAA",
                "Window": "1M",
                "Stock Return (%)": 12.0,
                "Benchmark Return (%)": 5.0,
                "Excess Return (%)": 7.0,
            },
            {
                "Stock": "BBB",
                "Window": "1M",
                "Stock Return (%)": 15.0,
                "Benchmark Return (%)": 5.0,
                "Excess Return (%)": 10.0,
            },
        ],
        "sector_comparison_available": True,
        "sector_comparison_reason": (
            "All selected stocks have configured sector membership."
        ),
        "sector_results": [
            {
                "Stock": "HINDUNILVR",
                "Window": "1M",
                "Stock Return (%)": 8.0,
                "Sector Return (%)": 3.0,
                "Sector Excess Return (%)": 5.0,
                "Common Sessions": 20,
                "Start Date": "2026-09-30",
                "End Date": "2026-10-30",
            }
        ],
    }


def test_streamlit_ui_exports_main_and_sector_csv(monkeypatch):
    displayed_text, downloads = _mock_streamlit(monkeypatch)

    result = _base_result()

    rs_results.display_results(result)

    assert len(downloads) == 2

    main_download = next(
        item for item in downloads
        if item["label"] == "Download Main Index CSV"
    )

    sector_download = next(
        item for item in downloads
        if item["label"] == "Download Sector Comparison CSV"
    )

    assert main_download["file_name"] == (
        "tradelab_main_index_rs.csv"
    )
    assert sector_download["file_name"] == (
        "tradelab_sector_rs.csv"
    )

    assert main_download["mime"] == "text/csv"
    assert sector_download["mime"] == "text/csv"

    main_csv = pd.read_csv(
        StringIO(main_download["data"].decode("utf-8-sig"))
    )

    sector_csv = pd.read_csv(
        StringIO(sector_download["data"].decode("utf-8-sig"))
    )

    assert "Rank" in main_csv.columns
    assert main_csv["Stock"].tolist() == ["BBB", "AAA"]
    assert main_csv["Rank"].tolist() == [1, 2]

    assert "Rank" in sector_csv.columns
    assert sector_csv["Stock"].tolist() == ["HINDUNILVR"]
    assert sector_csv["Rank"].tolist() == [1]


def test_sector_guard_failure_shows_reason_and_hides_sector_csv(
    monkeypatch,
):
    displayed_text, downloads = _mock_streamlit(monkeypatch)

    result = _base_result()
    result["sector_comparison_available"] = False
    result["sector_comparison_reason"] = (
        "Unverified sector membership: MARICO"
    )
    result["sector_results"] = []

    rs_results.display_results(result)

    combined_text = " ".join(displayed_text)

    assert "Unverified sector membership: MARICO" in combined_text

    labels = [item["label"] for item in downloads]

    assert "Download Main Index CSV" in labels
    assert "Download Sector Comparison CSV" not in labels


def test_sector_guard_pass_but_no_results_shows_no_data_message(
    monkeypatch,
):
    displayed_text, downloads = _mock_streamlit(monkeypatch)

    result = _base_result()
    result["sector_comparison_available"] = False
    result["sector_comparison_reason"] = (
        "All selected stocks have configured sector membership."
    )
    result["sector_results"] = []

    rs_results.display_results(result)

    combined_text = " ".join(displayed_text)

    assert "Sector Membership Guard" in combined_text
    assert "তুলনাযোগ্য ফলাফল পাওয়া যায়নি" in combined_text

    labels = [item["label"] for item in downloads]

    assert "Download Main Index CSV" in labels
    assert "Download Sector Comparison CSV" not in labels
