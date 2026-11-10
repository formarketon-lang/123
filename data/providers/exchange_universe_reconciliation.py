"""NSE/BSE cash-equity identity reconciliation.

Exchange universes are filtered independently.
ISIN is the cross-exchange identity key.
Sector classification is deliberately outside this module.
"""
from __future__ import annotations

import hashlib
import re
import zipfile

from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


REQUIRED = {"Symbol", "ISIN", "Company"}

METADATA_FIELDS = {
    "exchange",
    "source_url",
    "filename",
    "downloaded_at_utc",
    "trading_date",
    "sha256",
}

OFFICIAL_SOURCE_HOSTS = {
    "NSE": ("nseindia.com",),
    "BSE": ("bseindia.com",),
}

ALIASES = {
    "SYMBOL": "Symbol",
    "SECURITY ID": "Symbol",
    "TCKRSYMB": "Symbol",
    "SECURITY_CODE": "Security_Code",
    "SCRIP CODE": "Security_Code",
    "SCRIP CD": "Security_Code",
    "SECURITY CODE": "Security_Code",
    "ISIN": "ISIN",
    "ISIN NO": "ISIN",
    "ISIN NUMBER": "ISIN",
    "COMPANY": "Company",
    "PRODUCT_IDENTIFIER": "Product_Identifier",
    "NAME OF COMPANY": "Company",
    "COMPANY NAME": "Company",
    "SECURITY NAME": "Company",
    "FININSTRMNM": "Company",
}


def _clean_headers(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame.columns = [
        " ".join(
            str(c).replace("\ufeff", "").strip().upper().split()
        )
        for c in frame.columns
    ]
    return frame


def normalize_snapshot(data: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Snapshot is empty or invalid.")

    frame = _clean_headers(data)

    rename = {
        c: ALIASES[c]
        for c in frame.columns
        if c in ALIASES
    }
    frame = frame.rename(columns=rename)

    missing = REQUIRED.difference(frame.columns)

    if missing:
        raise ValueError(
            "Snapshot missing required columns: "
            + ", ".join(sorted(missing))
        )

    columns = ["Symbol", "ISIN", "Company"]

    if "Security_Code" in frame.columns:
        columns.append("Security_Code")

    if "Product_Identifier" in frame.columns:
        columns.append("Product_Identifier")

    frame = frame[columns].copy()

    for column in columns:
        frame[column] = (
            frame[column].astype("string").str.strip()
        )
        frame[column] = frame[column].replace(
            {"": pd.NA, "NAN": pd.NA, "NONE": pd.NA}
        )

    for column in ["Symbol", "ISIN"]:
        frame[column] = frame[column].str.upper()

    return frame.reset_index(drop=True)


def load_nse_equity_universe(
    path: str | Path,
) -> tuple[pd.DataFrame, dict]:
    """Read NSE EQUITY_L.csv and retain SERIES=EQ only."""
    path = Path(path)

    raw = pd.read_csv(
        path,
        dtype="string",
        low_memory=False,
        compression="infer",
    )
    raw = _clean_headers(raw)

    required = {
        "SYMBOL",
        "NAME OF COMPANY",
        "SERIES",
        "ISIN NUMBER",
    }

    missing = required.difference(raw.columns)

    if missing:
        raise ValueError(
            "NSE equity list missing columns: "
            + ", ".join(sorted(missing))
        )

    series = (
        raw["SERIES"].astype("string").str.strip().str.upper()
    )

    eq = raw.loc[series.eq("EQ")].copy()

    selected = eq.rename(
        columns={
            "SYMBOL": "Symbol",
            "NAME OF COMPANY": "Company",
            "ISIN NUMBER": "ISIN",
        }
    )

    selected["Security_Code"] = pd.NA

    result = normalize_snapshot(selected)

    return result, {
        "source_format": "NSE_EQUITY_LIST",
        "raw_rows": int(len(raw)),
        "selected_series": "EQ",
        "selected_rows": int(len(result)),
        "excluded_non_eq_rows": int(len(raw) - len(result)),
        "series_counts": {
            str(k): int(v)
            for k, v in series.value_counts(
                dropna=False
            ).items()
        },
    }


def load_nse_cm_diagnostic(
    path: str | Path,
) -> tuple[pd.DataFrame, dict]:
    """Read NSE CM security gzip as diagnostic only."""
    path = Path(path)

    raw = pd.read_csv(
        path,
        dtype="string",
        low_memory=False,
        compression="infer",
    )
    raw = _clean_headers(raw)

    required = {
        "TCKRSYMB",
        "FININSTRMNM",
        "ISIN",
        "SCTYSRS",
        "DELFLG",
    }

    missing = required.difference(raw.columns)

    if missing:
        raise ValueError(
            "NSE CM file missing columns: "
            + ", ".join(sorted(missing))
        )

    series = (
        raw["SCTYSRS"].astype("string").str.strip().str.upper()
    )

    delete_flag = (
        raw["DELFLG"].astype("string").str.strip().str.upper()
    )

    eq_active = raw.loc[
        series.eq("EQ") & delete_flag.eq("N")
    ].copy()

    selected = eq_active.rename(
        columns={
            "TCKRSYMB": "Symbol",
            "FININSTRMNM": "Company",
            "ISIN": "ISIN",
        }
    )

    result = normalize_snapshot(selected)

    return result, {
        "source_format": "NSE_CM_SECURITY_MASTER_DIAGNOSTIC",
        "raw_rows": int(len(raw)),
        "eq_series_rows": int(series.eq("EQ").sum()),
        "active_eq_rows_del_flag_n": int(len(result)),
        "deleted_eq_rows_del_flag_y": int(
            (series.eq("EQ") & delete_flag.eq("Y")).sum()
        ),
        "not_used_as_primary_listed_universe": True,
    }


def verify_zip_integrity(path: str | Path) -> bool:
    """Verify ZIP structure and every member CRC."""
    file_path = Path(path)

    if not file_path.is_file() or not zipfile.is_zipfile(file_path):
        return False

    try:
        with zipfile.ZipFile(file_path) as archive:
            if archive.testzip() is not None:
                return False
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return False

    return True


def load_bse_equity_universe(
    path: str | Path,
) -> tuple[pd.DataFrame, dict]:
    """Read BSE security-master ZIP and retain active equities."""
    path = Path(path)

    if not verify_zip_integrity(path):
        raise ValueError(
            f"BSE ZIP integrity verification failed: {path}"
        )

    with zipfile.ZipFile(path) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if Path(name).name.upper().startswith("BSE_EQ_SCRIP")
            and name.lower().endswith(".csv")
        ]

        if len(candidates) != 1:
            raise ValueError(
                "Expected exactly one BSE_EQ_SCRIP*.csv member; "
                + "found "
                + str(len(candidates))
            )

        member = candidates[0]

        with archive.open(member) as handle:
            raw = pd.read_csv(
                handle,
                dtype="string",
                low_memory=False,
            )

    raw = _clean_headers(raw)

    required = {
        "TCKRSYMB",
        "FININSTRMNM",
        "ISIN",
        "FININSTRMTP",
        "SCTYTPFLG",
        "STS",
        "UNQPDCTIDR",
    }

    missing = required.difference(raw.columns)

    if missing:
        raise ValueError(
            "BSE security master missing columns: "
            + ", ".join(sorted(missing))
        )

    mask = (
        raw["FININSTRMTP"]
        .astype("string").str.strip().str.upper().eq("E")
        & raw["SCTYTPFLG"]
        .astype("string").str.strip().str.upper().eq("EQ")
        & raw["STS"]
        .astype("string").str.strip().str.upper().eq("A")
    )

    active = raw.loc[mask].copy()

    selected = active.rename(
        columns={
            "TCKRSYMB": "Symbol",
            "FININSTRMNM": "Company",
            "ISIN": "ISIN",
            "UNQPDCTIDR": "Product_Identifier",
        }
    )

    result = normalize_snapshot(selected)

    counts = raw[
        ["FININSTRMTP", "SCTYTPFLG", "STS"]
    ].fillna("<NA>").value_counts()

    return result, {
        "source_format": "BSE_SECURITY_MASTER_ZIP",
        "zip_member": member,
        "raw_rows": int(len(raw)),
        "selected_filter": {
            "FinInstrmTp": "E",
            "SctyTpFlg": "EQ",
            "Sts": "A",
        },
        "selected_active_eq_rows": int(len(result)),
        "status_combinations_top": [
            {
                "FinInstrmTp": str(idx[0]),
                "SctyTpFlg": str(idx[1]),
                "Sts": str(idx[2]),
                "rows": int(value),
            }
            for idx, value in counts.head(12).items()
        ],
    }


def _is_approved_exchange_url(
    source_url: str,
    exchange: str,
) -> bool:
    if exchange not in OFFICIAL_SOURCE_HOSTS:
        return False

    try:
        parsed = urlparse(source_url)

        if parsed.scheme != "https":
            return False

        if not parsed.hostname:
            return False

        if parsed.username or parsed.password:
            return False

        if parsed.port not in (None, 443):
            return False

        host = parsed.hostname.lower().rstrip(".")

        return any(
            host == approved
            or host.endswith("." + approved)
            for approved in OFFICIAL_SOURCE_HOSTS[exchange]
        )

    except ValueError:
        return False


def validate_metadata(metadata: dict, exchange: str) -> bool:
    if not isinstance(metadata, dict):
        return False

    if exchange not in OFFICIAL_SOURCE_HOSTS:
        return False

    if METADATA_FIELDS.difference(metadata):
        return False

    if str(metadata["exchange"]).upper() != exchange:
        return False

    if not str(metadata["filename"]).strip():
        return False

    source_url = str(metadata["source_url"]).strip()

    if not _is_approved_exchange_url(source_url, exchange):
        return False

    if not re.fullmatch(
        r"[a-fA-F0-9]{64}",
        str(metadata["sha256"]),
    ):
        return False

    try:
        timestamp = datetime.fromisoformat(
            str(metadata["downloaded_at_utc"]).replace(
                "Z", "+00:00"
            )
        )

        if timestamp.tzinfo is None:
            return False

        date.fromisoformat(str(metadata["trading_date"]))

    except (ValueError, TypeError):
        return False

    return True


def verify_snapshot_checksum(
    path: str | Path,
    metadata: dict,
) -> bool:
    """Compare metadata SHA-256 with the actual file bytes."""
    if not isinstance(metadata, dict):
        return False

    expected = str(metadata.get("sha256", "")).lower()

    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        return False

    file_path = Path(path)

    if not file_path.is_file():
        return False

    digest = hashlib.sha256()

    try:
        with file_path.open("rb") as handle:
            for chunk in iter(
                lambda: handle.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)
    except OSError:
        return False

    return digest.hexdigest() == expected


def verify_snapshot_file(
    path: str | Path,
    exchange: str,
    expected_sha256: str | None = None,
) -> dict:
    """Verify snapshot bytes and optional independent expected hash."""
    file_path = Path(path)

    if not file_path.is_file():
        raise ValueError(f"Snapshot file not found: {file_path}")

    if exchange not in ("NSE", "BSE"):
        raise ValueError(f"Unsupported exchange: {exchange}")

    if exchange == "BSE" and not verify_zip_integrity(file_path):
        raise ValueError("BSE ZIP integrity verification failed.")

    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    actual = digest.hexdigest()

    if expected_sha256 is not None:
        expected = expected_sha256.strip().lower()

        if not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise ValueError(
                "Expected SHA-256 must contain 64 hex characters."
            )

        if actual != expected:
            raise ValueError(
                "Snapshot SHA-256 does not match expected hash."
            )

    return {
        "exchange": exchange,
        "filename": file_path.name,
        "sha256": actual,
        "checksum_verified_against_expected": (
            expected_sha256 is not None
        ),
        "zip_integrity_verified": exchange == "BSE",
    }


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
        r"IN[A-Z0-9]{10}",
        na=False,
    )

    symbol_count = frame["Symbol"].value_counts(dropna=False)
    isin_count = frame["ISIN"].value_counts(dropna=False)

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
    detail.loc[missing_identity, "Audit_Status"] = (
        "MISSING_IDENTITY"
    )

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
        nse,
        "NSE",
        nse_metadata,
    )

    bse_detail, bse_summary = audit_one_exchange(
        bse,
        "BSE",
        bse_metadata,
    )

    nse_isins = set(
        nse_detail.loc[nse_detail["Valid_ISIN"], "ISIN"]
    )

    bse_isins = set(
        bse_detail.loc[bse_detail["Valid_ISIN"], "ISIN"]
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
