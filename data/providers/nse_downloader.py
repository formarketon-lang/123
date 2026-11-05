
"""NSE historical equity downloader using Chrome TLS impersonation."""

from datetime import datetime
from pathlib import Path

import pandas as pd
from curl_cffi import requests


NSE_BASE_URL = "https://www.nseindia.com"

NSE_OPTION_CHAIN_URL = f"{NSE_BASE_URL}/option-chain"

HTML_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": f"{NSE_BASE_URL}/option-chain",
}


def create_nse_session():
    """
    Create a Chrome-impersonated NSE session.

    Warm up the NSE homepage and option-chain page before
    calling historical API endpoints.

    No CAPTCHA or access-control challenge is bypassed.
    """

    session = requests.Session(impersonate="chrome")

    session.headers.update(HEADERS)

    # Step 1: Initialize NSE cookies using a browser-like request.
    homepage = session.get(
        NSE_BASE_URL,
        headers={
            "Accept": HTML_ACCEPT,
            "Referer": f"{NSE_BASE_URL}/",
        },
        timeout=30,
    )
    homepage.raise_for_status()

    # Step 2: Warm up the option-chain page in the same session.
    option_chain = session.get(
        NSE_OPTION_CHAIN_URL,
        headers={
            "Accept": HTML_ACCEPT,
            "Referer": f"{NSE_BASE_URL}/",
        },
        timeout=30,
    )
    option_chain.raise_for_status()

    # Step 3: Restore JSON headers for historical API requests.
    session.headers.update(HEADERS)

    return session


def download_equity_history(symbol, start_date, end_date):
    """
    Download historical NSE equity price data.

    Reject invalid and duplicate trading dates.
    Dates must use YYYY-MM-DD format.
    """

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid NSE equity symbol is required.")

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if start > end:
        raise ValueError("Start date cannot be after end date.")

    session = create_nse_session()

    url = f"{NSE_BASE_URL}/api/historical/cm/equity"

    params = {
        "symbol": symbol.strip().upper(),
        "series": '["EQ"]',
        "from": start.strftime("%d-%m-%Y"),
        "to": end.strftime("%d-%m-%Y"),
    }

    response = session.get(
        url,
        params=params,
        timeout=30,
    )
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
        raise ValueError(
            f"Unexpected NSE response. Missing: {missing}"
        )

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

    df = df[
        ["Date", "Open", "High", "Low", "Close", "Volume"]
    ].copy()

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    invalid_dates = int(df["Date"].isna().sum())

    if invalid_dates:
        raise ValueError(
            "NSE equity response contains "
            f"{invalid_dates} invalid or missing trading dates."
        )

    duplicate_dates = int(df["Date"].duplicated().sum())

    if duplicate_dates:
        raise ValueError(
            "Duplicate dates found in NSE equity data: "
            f"{duplicate_dates}. Data was not silently discarded."
        )

    for column in ["Open", "High", "Low", "Close", "Volume"]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.sort_values("Date").reset_index(drop=True)

    return df


def save_nse_csv(df, symbol):
    """Save downloaded data in the NSE raw-data folder."""

    output_dir = Path("data/raw/nse")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{symbol.upper()}_nse.csv"

    df.to_csv(output_file, index=False)

    return str(output_file)
