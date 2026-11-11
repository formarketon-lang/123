
"""Common market-data provenance metadata for TradeLab Pro."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class DataProvenance:
    symbol: str
    source: str
    exchange: str
    timeframe: str
    fetched_at_utc: str
    validation_status: str
    fallback_reason: str
    observation_start: Optional[str]
    observation_end: Optional[str]


def _utc_timestamp(value=None) -> str:
    """Return an ISO-8601 UTC timestamp."""

    timestamp = pd.Timestamp.now(tz="UTC") if value is None else pd.Timestamp(value)

    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")

    return timestamp.isoformat().replace("+00:00", "Z")


def build_data_provenance(
    data: pd.DataFrame,
    symbol: str,
    source: str,
    exchange: str,
    timeframe: str,
    fallback_reason: str = "",
    fetched_at_utc=None,
    validation_status: str = "PASS",
) -> DataProvenance:
    """Build a validated provenance record for market data."""

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame.")

    if data.empty:
        raise ValueError("Cannot create provenance for empty market data.")

    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("A valid symbol is required.")

    if not isinstance(source, str) or not source.strip():
        raise ValueError("A valid data source is required.")

    if not isinstance(exchange, str) or not exchange.strip():
        raise ValueError("A valid exchange is required.")

    if not isinstance(timeframe, str) or not timeframe.strip():
        raise ValueError("A valid timeframe is required.")

    status = str(validation_status).strip().upper()
    if status not in {"PASS", "REVIEW", "FAIL"}:
        raise ValueError("Invalid validation status.")

    if "Date" not in data.columns:
        raise ValueError("Market data must contain Date.")

    dates = pd.to_datetime(data["Date"], errors="coerce")

    if dates.isna().any():
        raise ValueError("Invalid observation dates found.")

    return DataProvenance(
        symbol=symbol.strip().upper(),
        source=source.strip().upper(),
        exchange=exchange.strip().upper(),
        timeframe=timeframe.strip(),
        fetched_at_utc=_utc_timestamp(fetched_at_utc),
        validation_status=status,
        fallback_reason=str(fallback_reason or "").strip(),
        observation_start=dates.min().date().isoformat(),
        observation_end=dates.max().date().isoformat(),
    )


def attach_data_provenance(
    data: pd.DataFrame,
    symbol: str,
    source: str,
    exchange: str,
    timeframe: str,
    fallback_reason: str = "",
    fetched_at_utc=None,
    validation_status: str = "PASS",
) -> pd.DataFrame:
    """Attach common provenance fields without modifying input data."""

    result = data.copy()

    provenance = build_data_provenance(
        data=result,
        symbol=symbol,
        source=source,
        exchange=exchange,
        timeframe=timeframe,
        fallback_reason=fallback_reason,
        fetched_at_utc=fetched_at_utc,
        validation_status=validation_status,
    )

    result["Fetched At UTC"] = provenance.fetched_at_utc
    result["Validation Status"] = provenance.validation_status
    result["Observation Start"] = provenance.observation_start
    result["Observation End"] = provenance.observation_end

    return result
  
