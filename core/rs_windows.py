"""
TradeLab Pro - Relative Strength Return Windows

Supports standard and user-defined calendar-day return windows.
"""

from datetime import timedelta


WINDOW_DAYS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
}


def _resolve_window(item):
    """Resolve a standard or custom window into (label, days)."""

    if item in WINDOW_DAYS:
        return item, WINDOW_DAYS[item]

    if isinstance(item, str) and item.startswith("CUSTOM_") and item.endswith("D"):
        raw_days = item[len("CUSTOM_"):-1]

        try:
            days = int(raw_days)
        except ValueError:
            return None, None

        if 2 <= days <= 3650:
            return f"Custom {days}D", days

    return None, None


def build_windows(start_date, end_date, additional_windows=None):
    """
    Build selected-period, standard and custom return windows.

    Custom format: CUSTOM_45D, CUSTOM_120D, etc.
    """

    if end_date <= start_date:
        raise ValueError("End Date must be after Start Date.")

    if additional_windows is None:
        additional_windows = []

    if not isinstance(additional_windows, (list, tuple, set)):
        raise TypeError(
            "Additional windows must be a list, tuple, or set."
        )

    windows = {
        "Selected Period": (start_date, end_date),
    }

    for item in additional_windows:
        label, days = _resolve_window(item)

        if days is None:
            continue

        window_start = end_date - timedelta(days=days)

        if window_start >= start_date:
            windows[label] = (window_start, end_date)

    return windows
    
