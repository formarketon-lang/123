"""Independent NSE and BSE cash-equity universe reconciliation."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urlparse

import pandas as pd


REQUIRED = {"Symbol", "ISIN", "Company"}
METADATA_FIELDS = {
    "exchange", "source_url", "filename",
    "downloaded_at_utc", "trading_date", "sha256",
}

ALIASES = {
    "SYMBOL": "Symbol",
    "SECURITY ID": "Symbol",
    "SCRIP CD": "Symbol",
    "SCRIP CODE": "Symbol",
    "TCKRSYMB": "Symbol",
    "ISIN": "ISIN",
    "ISIN NO": "ISIN",
    "ISIN NUMBER": "ISIN",
    "NAME OF COMPANY": "Company",
    "COMPANY NAME": "Company",
    "SECURITY NAME": "Company",
    "FININSTRMNM": "Company",
}


def normalize_snapshot(data: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Snapshot is empty or invalid.")

    frame = data.copy()
    rename = {}

    for column in frame.columns:
        key = " ".join(
            str(column).replace("\ufeff", "")
            .strip().upper().split()
        )
        if key in ALIASES:
            rename[column] = ALIASES[key]

    frame = frame.rename(columns=rename)

    missing = REQUIRED.difference(frame.columns)
    if missing:
        raise ValueError(
            "Snapshot missing required columns: "
            + ", ".join(sorted(missing))
        )

    frame = frame[["Symbol", "ISIN", "Company"]].copy()

    for column in REQUIRED:
        frame[column] = (
            frame[column].astype("string").str.strip()
        )

    for column in ["Symbol", "ISIN"]:
        frame[column] = frame[column].str.upper()

    return frame.reset_index(drop=True)


def validate_metadata(metadata: dict, exchange: str) -> bool:
    if not isinstance(metadata, dict):
        return False

    if METADATA_FIELDS.difference(metadata):
        return False

    if str(metadata["exchange"]).upper() != exchange:
        return False

    if not str(metadata["filename"]).strip():
        return False

    parsed = urlparse(str(metadata["source_url"]))
    if parsed.scheme != "https" or not parsed.netloc:
        return False

    if not re.fullmatch(
        r"[a-fA-F0-9]{64}", str(metadata["sha256"])
    ):
        return False

    try:
        timestamp = datetime.fromisoformat(
            str(metadata["downloaded_at_utc"]).replace("Z", "+00:00")
        )
        if timestamp.tzinfo is None:
            return False

        date.fromisoformat(str(metadata["trading_date"]))
    except (ValueError, TypeError):
        return False

    return True


def audit_one_exchange(
    data: pd.DataFrame,
    exchange: str,
    metadata: dict,
) -> tuple[pd.DataFrame, dict]:

    frame = normalize_snapshot(data)

    missing_identity = (
        frame[["Symbol", "ISIN", "Company"]].isna().any(axis=1)
        | frame[["Symbol", "ISIN", "Company"]].eq("").any(axis=1)
    )

    valid_isin = frame["ISIN"].str.fullmatch(
        r"IN[A-Z0-9]{10}", na=False
    )

    symbol_count = frame["Symbol"].value_counts()
    isin_count = frame["ISIN"].value_counts()

    detail = frame.copy()
    detail["Exchange"] = exchange
    detail["Duplicate_Symbol"] = (
        detail["Symbol"].map(symbol_count).gt(1)
    )
    detail["Duplicate_ISIN"] = (
        detail["ISIN"].map(isin_count).gt(1)
    )
    detail["Valid_ISIN"] = valid_isin
    detail["Missing_Identity"] = missing_identity

    detail["Audit_Status"] = "PASS"
    detail.loc[~valid_isin, "Audit_Status"] = "INVALID_ISIN"
    detail.loc[missing_identity, "Audit_Status"] = "MISSING_IDENTITY"
    detail.loc[
        detail["Duplicate_Symbol"] | detail["Duplicate_ISIN"],
        "Audit_Status",
    ] = "DUPLICATE_IDENTITY"

    metadata_valid = validate_metadata(metadata, exchange)

    issue_rows = int(detail["Audit_Status"].ne("PASS").sum())

    summary = {
        "exchange": exchange,
        "input_rows": len(detail),
        "unique_symbols": int(detail["Symbol"].nunique()),
        "unique_isins": int(detail["ISIN"].nunique()),
        "duplicate_symbol_rows": int(
            detail["Duplicate_Symbol"].sum()
        ),
        "duplicate_isin_rows": int(
            detail["Duplicate_ISIN"].sum()
        ),
        "invalid_isin_rows": int((~valid_isin).sum()),
        "missing_identity_rows": int(missing_identity.sum()),
        "issue_rows": issue_rows,
        "metadata_valid": metadata_valid,
        "status": (
            "PASS"
            if issue_rows == 0 and metadata_valid
            else "REVIEW"
        ),
        "mapping_eligible": False,
        "sector_mapping_activated": False,
    }

    return detail, summary


def build_exchange_universe_reconciliation(
    nse: pd.DataFrame,
    bse: pd.DataFrame,
    nse_metadata: dict,
    bse_metadata: dict,
) -> tuple[pd.DataFrame, dict]:

    nse_detail, nse_summary = audit_one_exchange(
        nse, "NSE", nse_metadata
    )
    bse_detail, bse_summary = audit_one_exchange(
        bse, "BSE", bse_metadata
    )

    nse_isins = set(
        nse_detail.loc[
            nse_detail["Valid_ISIN"], "ISIN"
        ]
    )
    bse_isins = set(
        bse_detail.loc[
            bse_detail["Valid_ISIN"], "ISIN"
        ]
    )

    common_isins = nse_isins.intersection(bse_isins)

    combined = pd.concat(
        [nse_detail, bse_detail],
        ignore_index=True,
    )

    summary = {
        "status": (
            "PASS"
            if nse_summary["status"] == "PASS"
            and bse_summary["status"] == "PASS"
            else "REVIEW"
        ),
        "nse": nse_summary,
        "bse": bse_summary,
        "cross_listed_isin_count": len(common_isins),
        "cross_listed_isins": sorted(common_isins),
        "exchange_universes_kept_separate": True,
        "classification_inferred": False,
        "mapping_eligible": False,
        "sector_mapping_activated": False,
    }

    return combined, summary