"""Production downloader for NSE CM UDiFF final equity bhavcopy."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from io import BytesIO
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd

from data.providers.nse_downloader import create_nse_session
from data.providers.nse_udiff_bhavcopy import (
    normalize_nse_udiff_equity_bhavcopy,
    read_nse_udiff_bhavcopy,
)


NSE_UDIFF_BHAVCOPY_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{yyyymmdd}_F_0000.csv.zip"
)

# ISO-tag mapping used by the NSE CM UDiFF Bhavcopy.
# Keep this map isolated and require the exact expected raw tags.
NSE_CM_UDIFF_EQUITY_COLUMN_MAP = {
    "Date": "TradDt",
    "Symbol": "TckrSymb",
    "ISIN": "ISIN",
    "Series": "SctySrs",
    "Previous Close": "PrvsClsgPric",
    "Current Close": "ClsPric",
}

REQUIRED_RAW_FIELDS = {
    "TradDt",
    "Sgmt",
    "Src",
    "FinInstrmTp",
    "FinInstrmId",
    "SsnId",
    "ISIN",
    "TckrSymb",
    "SctySrs",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "PrvsClsgPric",
    "TtlTradgVol",
}


class NSEUdiFFDownloadError(RuntimeError):
    """Raised when the official NSE CM UDiFF file cannot be verified."""


def _as_trade_date(value: date | str) -> date:
    """Validate a calendar date used in the NSE archive filename."""

    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("A valid NSE trade date is required.") from exc

    if pd.isna(parsed):
        raise ValueError("A valid NSE trade date is required.")

    return parsed.date()


def _text_column(data: pd.DataFrame, column: str) -> pd.Series:
    """Return a stripped uppercase text field without inventing values."""

    return data[column].astype("string").str.strip().str.upper()


def _numeric_column(
    data: pd.DataFrame,
    source_column: str,
    output_column: str,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> pd.Series:
    """Parse numeric UDiFF values and reject malformed/non-finite values."""

    raw = data[source_column].astype("string").str.strip()
    cleaned = raw.str.replace(",", "", regex=False).replace("", pd.NA)
    values = pd.to_numeric(cleaned, errors="coerce")

    if values.isna().any():
        raise NSEUdiFFDownloadError(
            f"UDiFF contains missing or invalid {output_column} values."
        )

    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise NSEUdiFFDownloadError(
            f"UDiFF {output_column} values must be finite."
        )

    if positive and (values <= 0).any():
        raise NSEUdiFFDownloadError(
            f"UDiFF {output_column} values must be positive."
        )

    if non_negative and (values < 0).any():
        raise NSEUdiFFDownloadError(
            f"UDiFF {output_column} values cannot be negative."
        )

    return values


def normalize_nse_cm_udiff_equity(
    raw_data: pd.DataFrame,
    *,
    trade_date: date | str,
    fetched_at_utc: str,
) -> pd.DataFrame:
    """Normalize only NSE CM / STK / EQ rows using explicit ISO tags."""

    expected_date = pd.Timestamp(_as_trade_date(trade_date)).normalize()

    if not isinstance(raw_data, pd.DataFrame) or raw_data.empty:
        raise NSEUdiFFDownloadError("NSE UDiFF raw data is empty or invalid.")

    missing = REQUIRED_RAW_FIELDS.difference(raw_data.columns)
    if missing:
        raise NSEUdiFFDownloadError(
            "Official UDiFF response is missing required ISO tags: "
            + ", ".join(sorted(missing))
        )

    segment = _text_column(raw_data, "Sgmt")
    source = _text_column(raw_data, "Src")
    instrument_type = _text_column(raw_data, "FinInstrmTp")
    series = _text_column(raw_data, "SctySrs")

    # The F filename denotes a final bhavcopy; interim I1/I2 files
    # must not enter the production daily close series.
    session_ids = _text_column(raw_data, "SsnId")
    if (
        session_ids.isna().any()
        or session_ids.nunique() != 1
        or session_ids.iloc[0] not in {"F1", "F2"}
    ):
        raise NSEUdiFFDownloadError(
            "NSE final UDiFF file must contain one F1/F2 session only."
        )

    # Cash-equity only. No FO/CD/COM rows and no non-EQ series.
    mask = (
        segment.eq("CM")
        & source.eq("NSE")
        & instrument_type.eq("STK")
        & series.eq("EQ")
    )
    equity = raw_data.loc[mask].copy()

    if equity.empty:
        raise NSEUdiFFDownloadError(
            "NSE UDiFF file contains no NSE CM STK EQ rows."
        )

    dates = pd.to_datetime(
        equity["TradDt"],
        format="%Y-%m-%d",
        errors="coerce",
    ).dt.normalize()

    if dates.isna().any() or dates.nunique() != 1:
        raise NSEUdiFFDownloadError(
            "NSE UDiFF EQ rows must contain one valid trade date."
        )

    if dates.iloc[0] != expected_date:
        raise NSEUdiFFDownloadError(
            "NSE UDiFF trade date does not match requested date."
        )

    normalized = normalize_nse_udiff_equity_bhavcopy(
        equity,
        NSE_CM_UDIFF_EQUITY_COLUMN_MAP,
        fetched_at_utc=fetched_at_utc,
    )

    instrument_ids = _text_column(equity, "FinInstrmId")
    if (
        instrument_ids.isna().any()
        or not instrument_ids.str.fullmatch(r"\d+").all()
        or instrument_ids.duplicated().any()
    ):
        raise NSEUdiFFDownloadError(
            "NSE UDiFF Instrument ID values must be unique numeric identifiers."
        )

    extras = pd.DataFrame({
        "Symbol": _text_column(equity, "TckrSymb"),
        "Instrument ID": instrument_ids,
        "Open": _numeric_column(equity, "OpnPric", "Open", positive=True),
        "High": _numeric_column(equity, "HghPric", "High", positive=True),
        "Low": _numeric_column(equity, "LwPric", "Low", positive=True),
        "Volume": _numeric_column(
            equity, "TtlTradgVol", "Volume", non_negative=True
        ),
    })

    if extras["Symbol"].duplicated().any():
        raise NSEUdiFFDownloadError(
            "NSE UDiFF contains duplicate EQ symbols."
        )

    merged = normalized.merge(
        extras,
        on="Symbol",
        how="left",
        validate="one_to_one",
    )

    if merged[["Open", "High", "Low", "Volume"]].isna().any().any():
        raise NSEUdiFFDownloadError(
            "Normalized UDiFF rows lost OHLCV values during identity join."
        )

    # Previous Close belongs to the prior session and must not be
    # included in the current session's OHLC candle consistency check.
    invalid_high = merged["High"] < merged[
        ["Open", "Low", "Current Close"]
    ].max(axis=1)
    invalid_low = merged["Low"] > merged[
        ["Open", "High", "Current Close"]
    ].min(axis=1)

    if invalid_high.any() or invalid_low.any():
        raise NSEUdiFFDownloadError(
            "NSE UDiFF contains inconsistent OHLC values."
        )

    return merged.sort_values("Symbol").reset_index(drop=True)


def download_nse_cm_udiff_equity_bhavcopy(
    trade_date: date | str,
    *,
    session=None,
    timeout: int = 60,
) -> dict:
    """Download, parse and normalize the official NSE final CM UDiFF ZIP.

    The fetch timestamp is captured immediately after the HTTP response
    returns. The raw ZIP bytes and URL are returned for downstream hashing
    and provenance audit. No test timestamp or fallback source is used.
    """

    parsed_date = _as_trade_date(trade_date)
    date_token = parsed_date.strftime("%Y%m%d")
    filename = (
        f"BhavCopy_NSE_CM_0_0_0_{date_token}_F_0000.csv.zip"
    )
    source_url = NSE_UDIFF_BHAVCOPY_URL_TEMPLATE.format(
        yyyymmdd=date_token
    )

    client = session or create_nse_session()

    try:
        response = client.get(
            source_url,
            headers={
                "Accept": "application/zip,application/octet-stream,*/*",
                "Referer": "https://www.nseindia.com/all-reports",
            },
            timeout=timeout,
        )
        fetched_at_utc = (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        response.raise_for_status()
    except Exception as exc:
        raise NSEUdiFFDownloadError(
            f"Official NSE UDiFF download failed for {date_token}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    final_url = getattr(response, "url", None) or source_url
    parsed_url = urlparse(final_url)

    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "nsearchives.nseindia.com"
    ):
        raise NSEUdiFFDownloadError(
            "UDiFF response did not originate from the official NSE archive host."
        )

    source_bytes = response.content
    if not isinstance(source_bytes, bytes) or not source_bytes.startswith(b"PK"):
        raise NSEUdiFFDownloadError(
            "NSE UDiFF endpoint did not return a ZIP archive."
        )

    try:
        with ZipFile(BytesIO(source_bytes)) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise NSEUdiFFDownloadError(
                    f"NSE UDiFF ZIP contains a corrupt member: {corrupt_member}"
                )
    except BadZipFile as exc:
        raise NSEUdiFFDownloadError(
            "NSE UDiFF response is not a valid ZIP archive."
        ) from exc

    raw_data = read_nse_udiff_bhavcopy(source_bytes)
    normalized = normalize_nse_cm_udiff_equity(
        raw_data,
        trade_date=parsed_date,
        fetched_at_utc=fetched_at_utc,
    )

    return {
        "raw_bytes": source_bytes,
        "raw_data": raw_data,
        "normalized": normalized,
        "source": "NSE",
        "exchange": "NSE",
        "source_url": source_url,
        "source_filename": filename,
        "fetched_at_utc": fetched_at_utc,
        "observation_date": parsed_date.isoformat(),
        "sha256": hashlib.sha256(source_bytes).hexdigest(),
        "schema_mapping_status": "REVIEW",
    }
