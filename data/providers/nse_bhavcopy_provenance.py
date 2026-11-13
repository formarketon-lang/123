
"""Provenance and coverage audit for NSE CM-UDiFF Bhavcopy."""

from __future__ import annotations

import hashlib

import pandas as pd

from data.providers.nse_bhavcopy_mii_validation import (
    reconcile_bhavcopy_with_mii,
)


class NSEBhavcopyProvenanceError(ValueError):
    """Raised when NSE Bhavcopy provenance cannot be established."""


def audit_nse_bhavcopy_provenance(
    bhavcopy: pd.DataFrame,
    universe: pd.DataFrame,
    source_bytes: bytes,
    source_filename: str,
) -> dict:
    """Audit raw archive provenance and MII coverage.

    The official UDiFF schema remains explicitly UNVERIFIED until
    the official NSE catalogue/readme evidence is checked.
    Therefore this audit cannot return an overall PASS yet.
    """

    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise NSEBhavcopyProvenanceError(
            "Original NSE Bhavcopy archive bytes are required."
        )

    if (
        not isinstance(source_filename, str)
        or not source_filename.strip()
        or "/" in source_filename
        or "\\" in source_filename
        or not source_filename.lower().endswith(".zip")
    ):
        raise NSEBhavcopyProvenanceError(
            "A valid NSE Bhavcopy ZIP filename is required."
        )

    if not isinstance(bhavcopy, pd.DataFrame) or bhavcopy.empty:
        raise NSEBhavcopyProvenanceError(
            "Normalized NSE Bhavcopy observations are required."
        )

    if not isinstance(universe, pd.DataFrame) or universe.empty:
        raise NSEBhavcopyProvenanceError(
            "Dated NSE MII universe is required."
        )

    reconciliation = reconcile_bhavcopy_with_mii(
        bhavcopy=bhavcopy,
        universe=universe,
    )

    source_sha256 = hashlib.sha256(source_bytes).hexdigest()

    audit_reasons = [
        "OFFICIAL_UDIFF_SCHEMA_MAPPING_UNVERIFIED"
    ]

    if reconciliation["coverage_status"] != "PASS":
        audit_reasons.append(
            "MII_SYMBOL_COVERAGE_INCOMPLETE"
        )

    return {
        "source": "NSE",
        "source_format": "NSE_CM_UDIFF_ZIP",
        "source_filename": source_filename.strip(),
        "source_sha256": source_sha256,
        "source_size_bytes": len(source_bytes),
        "source_provenance_status": "PASS",
        "observation_date": reconciliation["observation_date"],
        "mii_snapshot_date": reconciliation["mii_snapshot_date"],
        "raw_observation_rows": len(bhavcopy),
        "observed_symbols": reconciliation["observed_symbols"],
        "expected_symbols": reconciliation["expected_symbols"],
        "missing_symbols": reconciliation["missing_symbols"],
        "missing_count": reconciliation["missing_count"],
        "coverage_pct": reconciliation["coverage_pct"],
        "identity_status": reconciliation["identity_status"],
        "coverage_status": reconciliation["coverage_status"],
        "schema_mapping_status": "UNVERIFIED",
        "audit_status": "REVIEW",
        "audit_reasons": audit_reasons,
    }
  
