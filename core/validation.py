
import pandas as pd


def validate_price_data(data):
    """Validate basic OHLCV price data."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError("Price data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Price data is empty.")

    required = ["Date", "Open", "High", "Low", "Close", "Volume"]

    missing = [
        column for column in required
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    return True
  
