
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


NSE_BASE_URL = "https://www.nseindia.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nseindia.com/",
}


def create_nse_session():
    """Create a session and initialize NSE cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(NSE_BASE_URL, timeout=20)
    response.raise_for_status()

    return session


def download_equity_history(symbol, start_date, end_date):
    """
    Download historical NSE equity price data.

    Dates must use YYYY-MM-DD format.
    Returns a DataFrame or raises an error.
    """

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if start > end:
        raise ValueError("Start date cannot be after end date.")

    session = create_nse_session()

    url = f"{NSE_BASE_URL}/api/historical/cm/equity"

    params = {
        "symbol": symbol.upper(),
        "series": '["EQ"]',
        "from": start.strftime("%d-%m-%Y"),
        "to": end.strftime("%d-%m-%Y"),
    }

    response = session.get(url, params=params, timeout=30)
    response.raise_for_status()

    payload = response.json()
    records = payload.get("data", [])

    if not records:
        raise ValueError(
            f"No NSE data returned for {symbol}. "
            "Check symbol, dates, or NSE access."
        )

    df = pd.DataFrame(records)

    required_columns = {
        "CH_TIMESTAMP",
        "CH_OPENING_PRICE",
        "CH_TRADE_HIGH_PRICE",
        "CH_TRADE_LOW_PRICE",
        "CH_CLOSING_PRICE",
        "CH_TOT_TRADED_QTY",
    }

    missing = required_columns.difference(df.columns)

    if missing:
        raise ValueError(f"Unexpected NSE response. Missing: {missing}")

    df = df.rename(
        columns={
            "CH_TIMESTAMP": "Date",
            "CH_OPENING_PRICE": "Open",
            "CH_TRADE_HIGH_PRICE": "High",
            "CH_TRADE_LOW_PRICE": "Low",
            "CH_CLOSING_PRICE": "Close",
            "CH_TOT_TRADED_QTY": "Volume",
        }
    )

    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for column in ["Open", "High", "Low", "Close", "Volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["Date"]).sort_values("Date")
    df = df.drop_duplicates(subset=["Date"], keep="last")
    df = df.reset_index(drop=True)

    return df


def save_nse_csv(df, symbol):
    """Save downloaded data in the NSE raw-data folder."""

    output_dir = Path("data/raw/nse")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{symbol.upper()}_nse.csv"

    df.to_csv(output_file, index=False)

    return str(output_file)
  
