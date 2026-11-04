
"""Download and normalize the official NSE cash-equity security list."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
import requests


NSE_EQUITY_MASTER_URL = (
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
)

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/octet-stream,*/*",
    "Referer": "https://www.nseindia.com/",
}


def _clean_column_name(value: object) -> str:
    return " ".join(
        str(value).replace("\ufeff", "").strip().upper().split()
    )


def normalize_nse_equity_master(
    data: pd.DataFrame,
    equity_series_only: bool = True,
) -> pd.DataFrame:
    """Validate and normalize an NSE equity-master DataFrame."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("NSE equity master is empty or invalid.")

    frame = data.copy()
    frame.columns = [
        _clean_column_name(column) for column in frame.columns
    ]

    aliases = {
        "SYMBOL": "Symbol",
        "NAME OF COMPANY": "Company",
        "SERIES": "Series",
        "DATE OF LISTING": "Listing Date",
        "ISIN NUMBER": "ISIN",
        "FACE VALUE": "Face Value",
    }

    frame = frame.rename(columns=aliases)

    required = ["Symbol", "Company", "Series", "ISIN"]
    missing = [
        column for column in required
        if column not in frame.columns
    ]

    if missing:
        raise ValueError(
            "Unexpected NSE equity-master format; missing columns: "
            + ", ".join(missing)
        )

    output_columns = [
        column for column in [
            "Symbol", "Company", "Series",
            "Listing Date", "ISIN", "Face Value",
        ]
        if column in frame.columns
    ]

    frame = frame[output_columns].copy()

    for column in ["Symbol", "Company", "Series", "ISIN"]:
        frame[column] = frame[column].astype("string").str.strip()

    frame = frame.dropna(
        subset=["Symbol", "Company", "Series", "ISIN"]
    )

    frame = frame[
        (frame["Symbol"] != "")
        & (frame["Company"] != "")
        & (frame["ISIN"] != "")
    ]

    if equity_series_only:
        frame = frame[
            frame["Series"].str.upper() == "EQ"
        ]

    if "Listing Date" in frame.columns:
        frame["Listing Date"] = pd.to_datetime(
            frame["Listing Date"],
            errors="coerce",
            dayfirst=True,
        )

    if "Face Value" in frame.columns:
        frame["Face Value"] = pd.to_numeric(
            frame["Face Value"],
            errors="coerce",
        )

    frame["Symbol"] = frame["Symbol"].str.upper()
    frame["Series"] = frame["Series"].str.upper()
    frame["Exchange"] = "NSE"
    frame["Source"] = "NSE Official Equity Master"

    frame = frame.drop_duplicates(
        subset=["Symbol", "Series", "ISIN"],
        keep="last",
    )

    frame = frame.sort_values("Symbol").reset_index(drop=True)

    if frame.empty:
        raise ValueError(
            "NSE equity master contains no eligible EQ securities."
        )

    return frame


def fetch_nse_equity_universe(
    timeout: int = 30,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Fetch the latest NSE equity master and return EQ securities."""

    client = session or requests.Session()
    client.headers.update(NSE_HEADERS)

    home = client.get(
        "https://www.nseindia.com",
        timeout=timeout,
    )
    home.raise_for_status()

    response = client.get(
        NSE_EQUITY_MASTER_URL,
        timeout=timeout,
    )
    response.raise_for_status()

    try:
        raw = pd.read_csv(
            BytesIO(response.content),
            dtype="string",
        )
    except Exception as exc:
        raise ValueError(
            "Could not parse the NSE equity-master CSV."
        ) from exc

    return normalize_nse_equity_master(
        raw,
        equity_series_only=True,
    )
