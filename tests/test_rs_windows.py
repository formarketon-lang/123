from datetime import date

import pytest

from core.rs_windows import build_windows


def test_build_selected_and_standard_windows():
    result = build_windows(
        date(2025, 1, 1),
        date(2026, 1, 1),
        ["1M", "3M"],
    )

    assert "Selected Period" in result
    assert "1M" in result
    assert "3M" in result


def test_build_custom_45_day_window():
    result = build_windows(
        date(2025, 1, 1),
        date(2026, 1, 1),
        ["CUSTOM_45D"],
    )

    assert "Custom 45D" in result

    start, end = result["Custom 45D"]

    assert (end - start).days == 45


def test_build_multiple_custom_windows():
    result = build_windows(
        date(2025, 1, 1),
        date(2026, 1, 1),
        ["CUSTOM_30D", "CUSTOM_120D"],
    )

    assert "Custom 30D" in result
    assert "Custom 120D" in result


def test_custom_window_outside_selected_period_is_skipped():
    result = build_windows(
        date(2025, 12, 1),
        date(2026, 1, 1),
        ["CUSTOM_90D"],
    )

    assert "Custom 90D" not in result


def test_invalid_custom_window_is_ignored():
    result = build_windows(
        date(2025, 1, 1),
        date(2026, 1, 1),
        ["CUSTOM_1D", "CUSTOM_4000D", "CUSTOM_XD"],
    )

    assert len(result) == 1


def test_reversed_dates_are_rejected():
    with pytest.raises(ValueError):
        build_windows(
            date(2026, 1, 1),
            date(2025, 1, 1),
        )
