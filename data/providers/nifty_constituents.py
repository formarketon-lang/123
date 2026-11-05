
"""NSE Indices constituent-list provider.

Primary source: Official Nifty Indices constituent CSV.
Initial integration: Nifty FMCG only.
"""

from io import BytesIO

import pandas as pd
import requests


SECTOR_CONSTITUENT_URLS = {
    "FMCG": (
        "https://www.niftyindices.com/IndexConstituent/"
        "ind_niftyfmcglist.csv"
    ),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/octet-stream,*/*",
    "Referer": "https://www.niftyindices.com/",
}


def normalize_sector_constituents(
    data: pd.DataFrame,
    sector: str,
) -> pd.DataFrame:
    """Normalize official constituent CSV data."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Constituent data is empty or invalid.")

    frame = data.copy()

    frame.columns = [
        " ".join(
            str(column)
            .replace("\ufeff", "")
            .strip()
            .lower()
            .split()
        )
        for column in frame.columns
    ]

    aliases = {
        "symbol": "Symbol",
        "company name": "Company",
        "company": "Company",
        "industry": "Industry",
        "series": "Series",
        "isin code": "ISIN",
        "isin": "ISIN",
    }

    frame = frame.rename(columns=aliases)

    if "Symbol" not in frame.columns:
        raise ValueError(
            "Unexpected constituent CSV format: Symbol column missing."
        )

    for column in ["Company", "Industry", "Series", "ISIN"]:
        if column not in frame.columns:
            frame[column] = pd.NA

    selected = [
        "Symbol",
        "Company",
        "Industry",
        "Series",
        "ISIN",
    ]

    frame = frame[selected].copy()

    for column in selected:
        frame[column] = (
            frame[column].astype("string").str.strip()
        )

    frame["Symbol"] = frame["Symbol"].str.upper()

    frame = frame[
        frame["Symbol"].notna()
        & frame["Symbol"].ne("")
    ]

    frame = frame.drop_duplicates(
        subset=["Symbol"],
        keep="last",
    )

    frame["Sector"] = sector
    frame["Index"] = f"Nifty {sector}"
    frame["Exchange"] = "NSE"
    frame["Source"] = "NSE Indices Official Constituents"

    frame = frame.sort_values("Symbol").reset_index(drop=True)

    if frame.empty:
        raise ValueError("No valid constituent symbols found.")

    return frame


def fetch_sector_constituents(
    sector: str,
    timeout: int = 30,
    session=None,
) -> pd.DataFrame:
    """Download and normalize a supported sector constituent list."""

    sector = str(sector).strip().upper()

    if sector not in SECTOR_CONSTITUENT_URLS:
        raise ValueError(
            f"No official constituent URL configured for {sector}."
        )

    client = session or requests

    response = client.get(
        SECTOR_CONSTITUENT_URLS[sector],
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()

    if not response.content:
        raise ValueError("Official constituent response is empty.")

    raw = pd.read_csv(
        BytesIO(response.content),
        dtype="string",
        low_memory=False,
    )

    return normalize_sector_constituents(raw, sector)
