
"""NSE CM-UDiFF Bhavcopy reader and strict equity normalizer.

Important:
- Does not assume unverified NSE raw column names.
- Caller must provide a verified raw-to-standard column mapping.
- Produces the standard observation format used by MII Breadth Service.
"""

from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile, ZipFile

import pandas as pd


class NSEUdiFFError(ValueError):
    """Raised when NSE UDiFF data is invalid or unverified."""


REQUIRED_MAP_FIELDS = {
    "Date",
    "Symbol",
    "ISIN",
    "Series",
    "Previous Close",
    "Current Close",
}


def read_nse_udiff_bhavcopy(content: bytes) -> pd.DataFrame:
    """Read exactly one CSV from an NSE CM-UDiFF ZIP archive."""

    if not isinstance(content, bytes) or not content:
        raise NSEUdiFFError("Bhavcopy ZIP content is empty.")

    try:
        with ZipFile(BytesIO(content)) as archive:
            csv_files = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv")
                and not name.startswith("__MACOSX/")
                and not name.startswith("/")
                and ".." not in name.split("/")
            ]

            if len(csv_files) != 1:
                raise NSEUdiFFError(
                    "Expected exactly one CSV in Bhavcopy ZIP; "
                    f"found {len(csv_files)}."
                )

            with archive.open(csv_files[0]) as file:
                data = pd.read_csv(
                    file,
                    dtype="string",
                    low_memory=False,
                )

    except BadZipFile as exc:
        raise NSEUdiFFError(
            "Invalid NSE Bhavcopy ZIP archive."
        ) from exc

    if data.empty:
        raise NSEUdiFFError("Bhavcopy CSV contains no rows.")

    cleaned = [
        str(column).replace("\ufeff", "").strip()
        for column in data.columns
    ]

    if len(cleaned) != len(set(cleaned)):
        raise NSEUdiFFError(
            "Bhavcopy CSV contains duplicate column names."
        )

    if any(not column for column in cleaned):
        raise NSEUdiFFError(
            "Bhavcopy CSV contains blank column names."
        )

    data.columns = cleaned
    return data


def normalize_nse_udiff_equity_bhavcopy(
    data: pd.DataFrame,
    column_map: dict[str, str],
) -> pd.DataFrame:
    """Convert raw UDiFF rows to the MII Breadth observation format.

    column_map keys must be standard field names and values must be
    raw column names confirmed from the official NSE UDiFF catalogue.
    """

    if not isinstance(data, pd.DataFrame) or data.empty:
        raise NSEUdiFFError("UDiFF data is empty or invalid.")

    if not isinstance(column_map, dict):
        raise NSEUdiFFError("A verified column mapping is required.")

    missing_map = REQUIRED_MAP_FIELDS.difference(column_map)
    if missing_map:
        raise NSEUdiFFError(
            "Verified mapping is incomplete: "
            + ", ".join(sorted(missing_map))
        )

    raw_columns = list(column_map.values())

    if any(
        not isinstance(name, str) or not name.strip()
        for name in raw_columns
    ):
        raise NSEUdiFFError("Raw column names must be non-empty strings.")

    if len(raw_columns) != len(set(raw_columns)):
        raise NSEUdiFFError(
            "One raw column cannot map to multiple standard fields."
        )

    missing_raw = set(raw_columns).difference(data.columns)
    if missing_raw:
        raise NSEUdiFFError(
            "UDiFF raw columns do not match verified mapping: "
            + ", ".join(sorted(missing_raw))
        )

    frame = pd.DataFrame({
        standard: data[raw].copy()
        for standard, raw in column_map.items()
    })

    for column in ["Symbol", "ISIN", "Series"]:
        frame[column] = (
            frame[column].astype("string").str.strip().str.upper()
        )

    frame["Date"] = pd.to_datetime(
        frame["Date"],
        errors="coerce",
        dayfirst=True,
    ).dt.normalize()

    for column in ["Previous Close", "Current Close"]:
        frame[column] = pd.to_numeric(
            frame[column].astype("string").str.replace(",", "", regex=False),
            errors="coerce",
        )

    if frame["Date"].isna().any():
        raise NSEUdiFFError("UDiFF contains invalid trade dates.")

    if frame["Date"].nunique() != 1:
        raise NSEUdiFFError(
            "Bhavcopy must contain exactly one trading date."
        )

    # This pipeline is specifically for NSE cash-equity EQ securities.
    frame = frame[frame["Series"] == "EQ"].copy()

    if frame.empty:
        raise NSEUdiFFError("No NSE EQ rows found in Bhavcopy.")

    if frame[["Symbol", "ISIN"]].isna().any().any():
        raise NSEUdiFFError("EQ rows contain missing Symbol or ISIN.")

    if frame["Symbol"].eq("").any() or frame["ISIN"].eq("").any():
        raise NSEUdiFFError("EQ rows contain blank Symbol or ISIN.")

    valid_isin = frame["ISIN"].str.fullmatch(
        r"IN[A-Z0-9]{10}",
        na=False,
    )
    if not valid_isin.all():
        raise NSEUdiFFError("EQ rows contain invalid Indian ISIN values.")

    if frame[["Previous Close", "Current Close"]].isna().any().any():
        raise NSEUdiFFError("EQ rows contain invalid closing prices.")

    if (
        frame[["Previous Close", "Current Close"]] <= 0
    ).any().any():
        raise NSEUdiFFError("EQ closing prices must be greater than zero.")

    if frame["Symbol"].duplicated().any():
        duplicates = sorted(
            frame.loc[
                frame["Symbol"].duplicated(keep=False),
                "Symbol",
            ].unique().tolist()
        )
        raise NSEUdiFFError(
            "Duplicate EQ symbols in Bhavcopy: "
            + ", ".join(duplicates)
        )

    frame["Source"] = "NSE"
    frame["Exchange"] = "NSE"
    frame["Timeframe"] = "1d"
    frame["Fallback Reason"] = ""
    frame["Validation Status"] = "PASS"

    output_columns = [
        "Date",
        "Symbol",
        "ISIN",
        "Series",
        "Previous Close",
        "Current Close",
        "Source",
        "Exchange",
        "Timeframe",
        "Fallback Reason",
        "Validation Status",
    ]

    return (
        frame[output_columns]
        .sort_values("Symbol")
        .reset_index(drop=True)
    )
