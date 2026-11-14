"""Production Market Intelligence service for NSE CM UDiFF breadth inputs."""

from __future__ import annotations

from datetime import date

import pandas as pd

from data.providers.nse_bhavcopy_mii_validation import (
    reconcile_bhavcopy_with_mii,
)
from data.providers.nse_bhavcopy_provenance import (
    audit_nse_bhavcopy_provenance,
)
from data.providers.nse_universe import fetch_nse_equity_universe
from data.providers.nse_udiff_downloader import (
    NSE_UDIFF_SCHEMA_MAPPING_VERIFIED,
    download_nse_cm_udiff_equity_bhavcopy,
)
from data.providers.nse_bhavcopy_provenance import (
    NSE_UDIFF_SCHEMA_REFERENCE_URL,
)
from services.market_intelligence.breadth_service import (
    analyze_nse_market_breadth,
)


class NSEBhavcopyServiceError(RuntimeError):
    """Raised when production NSE breadth inputs cannot be verified."""


def analyze_nse_market_breadth_from_udiff(
    observation_date: date | str,
    *,
    universe: pd.DataFrame | None = None,
    session=None,
) -> dict:
    """Fetch the official NSE UDiFF archive and run guarded breadth analysis.

    Only a date-matched NSE MII snapshot is accepted. Legacy/undated
    security masters are not silently substituted. Incomplete daily
    trading coverage remains REVIEW and never counts missing stocks
    as unchanged.
    """

    parsed_date = pd.Timestamp(observation_date)
    if pd.isna(parsed_date):
        raise ValueError("A valid observation date is required.")
    parsed_date = parsed_date.date()

    downloaded = download_nse_cm_udiff_equity_bhavcopy(
        parsed_date,
        session=session,
    )

    verified_universe = universe
    if verified_universe is None:
        verified_universe = fetch_nse_equity_universe(
            as_of_date=parsed_date,
            lookback_days=0,
        )

    if (
        not isinstance(verified_universe, pd.DataFrame)
        or verified_universe.empty
    ):
        raise NSEBhavcopyServiceError(
            "A dated NSE MII security master is required."
        )

    required_universe_fields = {
        "Symbol",
        "Instrument ID",
        "ISIN",
        "Series",
        "Exchange",
        "Source",
        "Universe As Of Date",
        "Universe Verification Status",
    }
    missing = required_universe_fields.difference(
        verified_universe.columns
    )
    if missing:
        raise NSEBhavcopyServiceError(
            "NSE MII universe is missing fields: "
            + ", ".join(sorted(missing))
        )

    statuses = (
        verified_universe["Universe Verification Status"]
        .astype("string")
        .str.strip()
        .str.upper()
    )
    if statuses.isna().any() or not statuses.eq("MII_DATED").all():
        raise NSEBhavcopyServiceError(
            "Only MII_DATED universe rows are accepted; legacy fallback is blocked."
        )

    snapshot_dates = pd.to_datetime(
        verified_universe["Universe As Of Date"],
        errors="coerce",
    ).dt.normalize()
    if snapshot_dates.isna().any() or snapshot_dates.nunique() != 1:
        raise NSEBhavcopyServiceError(
            "Every MII row must have one valid snapshot date."
        )
    if snapshot_dates.iloc[0].date() != parsed_date:
        raise NSEBhavcopyServiceError(
            "NSE MII snapshot date must match the Bhavcopy observation date."
        )

    normalized = downloaded["normalized"]

    reconciliation = reconcile_bhavcopy_with_mii(
        bhavcopy=normalized,
        universe=verified_universe,
    )

    audit = audit_nse_bhavcopy_provenance(
        bhavcopy=normalized,
        universe=verified_universe,
        source_bytes=downloaded["raw_bytes"],
        source_filename=downloaded["source_filename"],
        source_url=downloaded["source_url"],
        schema_reference_url=NSE_UDIFF_SCHEMA_REFERENCE_URL,
        schema_mapping_verified=NSE_UDIFF_SCHEMA_MAPPING_VERIFIED,
    )

    verified_observations = reconciliation["observations"]
    mii_source_provenance = dict(
        verified_universe.attrs.get("source_provenance", {})
    )
    point_in_time_status = str(
        mii_source_provenance.get("point_in_time_status", "REVIEW")
    ).strip().upper()
    if point_in_time_status not in {"PASS", "REVIEW", "BLOCKED", "UNAVAILABLE"}:
        raise NSEBhavcopyServiceError(
            "MII point-in-time availability status is invalid."
        )

    breadth = analyze_nse_market_breadth(
        stock_data=verified_observations,
        verified_universe=verified_universe,
        observation_date=parsed_date.isoformat(),
    )

    overall_status = (
        "PASS"
        if (
            reconciliation["identity_status"] == "PASS"
            and reconciliation["coverage_status"] == "PASS"
            and audit["audit_status"] == "PASS"
            and breadth["analysis_status"] == "PASS"
            and point_in_time_status == "PASS"
        )
        else "REVIEW"
    )

    return {
        "analysis_status": overall_status,
        "source": downloaded["source"],
        "source_url": downloaded["source_url"],
        "source_filename": downloaded["source_filename"],
        "source_sha256": downloaded["sha256"],
        "fetched_at_utc": downloaded["fetched_at_utc"],
        "mii_source_provenance": mii_source_provenance,
        "point_in_time_status": point_in_time_status,
        "observation_date": parsed_date.isoformat(),
        "normalized": normalized,
        "verified_observations": verified_observations,
        "unverified_observations": reconciliation[
            "unverified_observations"
        ],
        "universe": verified_universe,
        "reconciliation": reconciliation,
        "audit": audit,
        "breadth": breadth,
    }
