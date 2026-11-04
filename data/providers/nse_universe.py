"""NSE cash-equity universe provider.

Supports the legacy NSE EQUITY_L.csv and NSE MII security-master formats.
"""

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

MII_REQUIRED_COLUMNS = [
    "TCKRSYMB",
    "FININSTRMNM",
    "SCTYRS",
    "ISIN",
    "DELFLG",
    "ELGBLTYNRMLMKT",
    "SCTYSTSNRMLMKT",
]


def _clean_column_name(value: object) -> str:
    return " ".join(
        str(value).replace("\ufeff", "").strip().upper().split()
    )


def _valid_indian_isin(values: pd.Series) -> pd.Series:
    return values.str.fullmatch(r"IN[A-Z0-9]{10}", na=False)


def normalize_nse_mii_security_master(
    data: pd.DataFrame,
    equity_series_only: bool = True,
) -> pd.DataFrame:
    """Normalize official NSE MII security-master data.

    Default NSE universe:
    - EQ series
    - Active records (DelFlg=N)
    - Valid Indian ISIN
    - Normal-market eligibility = 1
    - Exclude suspended securities (status=3)
    - Exclude BSE-exclusive instruments (PrtdToTrad=2)
    - Exclude $ suffix and test/dummy instruments

    PrtdToTrad=0 is retained when other conditions pass.
    This matches the verified MII records of major NSE shares.
    """

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("NSE MII security master is empty or invalid.")

    frame = data.copy()
    frame.columns = [_clean_column_name(c) for c in frame.columns]

    missing = [
        column for column in MII_REQUIRED_COLUMNS
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            "Unexpected NSE MII format; missing columns: "
            + ", ".join(missing)
        )

    aliases = {
        "FININSTRMID": "Instrument ID",
        "TCKRSYMB": "Symbol",
        "FININSTRMNM": "Company",
        "SCTYRS": "Series",
        "LISTGDT": "Listing Date",
        "ISIN": "ISIN",
        "PARVAL": "Face Value",
        "ISSDCPTL": "Issued Capital",
        "DELFLG": "Delete Flag",
        "ELGBLTYNRMLMKT": "Normal Market Eligibility",
        "SCTYSTSNRMLMKT": "Normal Market Status",
        "PRTDTOTRAD": "Permitted to Trade",
    }

    frame = frame.rename(columns=aliases)

    selected = [
        "Instrument ID",
        "Symbol",
        "Company",
        "Series",
        "Listing Date",
        "ISIN",
        "Face Value",
        "Issued Capital",
        "Delete Flag",
        "Normal Market Eligibility",
        "Normal Market Status",
        "Permitted to Trade",
    ]

    frame = frame[
        [column for column in selected if column in frame.columns]
    ].copy()

    text_columns = [
        "Symbol",
        "Company",
        "Series",
        "ISIN",
        "Delete Flag",
        "Normal Market Eligibility",
        "Normal Market Status",
        "Permitted to Trade",
    ]

    for column in text_columns:
        if column in frame.columns:
            frame[column] = (
                frame[column].astype("string").str.strip()
            )

    for column in ["Symbol", "Series", "ISIN"]:
        frame[column] = frame[column].str.upper()

    if equity_series_only:
        frame = frame[frame["Series"] == "EQ"]

    frame = frame[frame["Delete Flag"] == "N"]

    frame = frame[
        frame["Normal Market Eligibility"] == "1"
    ]

    frame = frame[
        frame["Normal Market Status"] != "3"
    ]

    if "Permitted to Trade" in frame.columns:
        frame = frame[
            frame["Permitted to Trade"] != "2"
        ]

    frame = frame[
        frame["Symbol"].notna()
        & frame["Company"].notna()
        & frame["ISIN"].notna()
        & frame["Symbol"].ne("")
        & frame["Company"].ne("")
        & _valid_indian_isin(frame["ISIN"])
    ]

    frame = frame[
        ~frame["Symbol"].str.endswith("$", na=False)
        & ~frame["Symbol"].str.contains(
            r"NSETEST|DUMMY",
            case=False,
            regex=True,
            na=False,
        )
    ]

    # NSE MII dates use seconds from 01-Jan-1980.
    if "Listing Date" in frame.columns:
        listing_seconds = pd.to_numeric(
            frame["Listing Date"],
            errors="coerce",
        )

        frame["Listing Date"] = pd.to_datetime(
            listing_seconds,
            unit="s",
            origin="1980-01-01",
            errors="coerce",
        )

        frame.loc[
            listing_seconds.eq(0),
            "Listing Date",
        ] = pd.NaT

    for column in ["Face Value", "Issued Capital"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

    frame["Exchange"] = "NSE"
    frame["Source"] = "NSE MII Security Master"

    # Do not deduplicate by ISIN:
    # different symbols can share an ISIN during symbol changes.
    frame = frame.drop_duplicates(
        subset=["Symbol", "Series", "ISIN"],
        keep="last",
    )

    frame = frame.sort_values("Symbol").reset_index(drop=True)

    if frame.empty:
        raise ValueError(
            "NSE MII master contains no eligible NSE EQ securities."
        )

    return frame


def normalize_nse_equity_master(
    data: pd.DataFrame,
    equity_series_only: bool = True,
) -> pd.DataFrame:
    """Normalize legacy NSE or newer MII security-master data."""

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("NSE equity master is empty or invalid.")

    normalized_columns = {
        _clean_column_name(column) for column in data.columns
    }

    if "TCKRSYMB" in normalized_columns:
        return normalize_nse_mii_security_master(
            data,
            equity_series_only=equity_series_only,
        )

    frame = data.copy()
    frame.columns = [_clean_column_name(c) for c in frame.columns]

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
            "Symbol",
            "Company",
            "Series",
            "Listing Date",
            "ISIN",
            "Face Value",
        ]
        if column in frame.columns
    ]

    frame = frame[output_columns].copy()

    for column in required:
        frame[column] = (
            frame[column].astype("string").str.strip()
        )

    frame = frame.dropna(subset=required)

    frame = frame[
        frame["Symbol"].ne("")
        & frame["Company"].ne("")
        & frame["Series"].ne("")
        & frame["ISIN"].ne("")
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
    """Fetch the legacy NSE equity master and normalize it."""

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
    
