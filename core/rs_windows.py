
"""
TradeLab Pro - Relative Strength Return Windows

Builds the selected period and additional return windows.
"""

from datetime import timedelta


WINDOW_DAYS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
}


def build_windows(start_date, end_date, additional_windows=None):
    """
    Build selected-period and additional return windows.

    Returns:
        Dictionary:
        {
            "Selected Period": (start_date, end_date),
            "1M": (window_start, end_date),
        }
    """

    if end_date <= start_date:
        raise ValueError("End Date must be after Start Date.")

    if additional_windows is None:
        additional_windows = []

    if not isinstance(additional_windows, (list, tuple, set)):
        raise TypeError("Additional windows must be a list, tuple, or set.")

    windows = {
        "Selected Period": (start_date, end_date),
    }

    for item in additional_windows:

        days = WINDOW_DAYS.get(item)

        if days is None:
            continue

        window_start = end_date - timedelta(days=days)

        if window_start >= start_date:
            windows[item] = (window_start, end_date)

    return windows
