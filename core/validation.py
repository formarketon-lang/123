import math
import pandas as pd


def _normalize_utc_date(value, name):
    """Convert timezone-aware timestamps to UTC; preserve naive dates."""

    try:
        date = pd.Timestamp(value)

        if pd.isna(date):
            raise ValueError()

        if date.tzinfo is not None:
            date = date.tz_convert("UTC").tz_localize(None)

        return date.normalize()

    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} contains invalid dates.")


def normalize_price_data(data, name="Price"):
    """Validate and normalize Date and Close columns."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame.")

    if data.empty:
        raise ValueError(f"{name} data is empty.")

    if not {"Date", "Close"}.issubset(data.columns):
        raise ValueError(f"{name} needs Date and Close columns.")

    prices = data[["Date", "Close"]].copy()

    dates = [
        _normalize_utc_date(value, name)
        for value in prices["Date"]
    ]

    prices["Date"] = pd.to_datetime(dates)

    prices["Close"] = pd.to_numeric(
        prices["Close"], errors="coerce"
    )

    if prices["Close"].isna().any():
        raise ValueError(f"{name} has invalid Close prices.")

    if not all(math.isfinite(float(x)) for x in prices["Close"]):
        raise ValueError(f"{name} has infinite prices.")

    if (prices["Close"] <= 0).any():
        raise ValueError(f"{name} prices must be positive.")

    if prices["Date"].duplicated().any():
        raise ValueError(f"{name} has duplicate dates.")

    return prices.sort_values("Date").reset_index(drop=True)


def validate_date_range(start_date, end_date):
    """Validate requested analysis dates using consistent UTC rules."""

    start = _normalize_utc_date(start_date, "Start date")
    end = _normalize_utc_date(end_date, "End date")

    if end < start:
        raise ValueError("End date cannot be earlier than start date.")

    return start, end
    
