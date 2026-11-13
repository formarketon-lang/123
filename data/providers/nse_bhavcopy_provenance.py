
"""Provenance and coverage audit for NSE CM-UDiFF Bhavcopy."""

from __future__ import annotations

import hashlib
from io import BytesIO
from zipfile import BadZipFile, ZipFile

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
    """Audit archive hash, MII identity and coverage.

    Archive authenticity and official UDiFF schema mapping remain
    unverified until independent NSE evidence is available.
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

    try:
        with ZipFile(BytesIO(source_bytes)) as archive:
            if archive.testzip() is not None:
                raise NSEBhavcopyProvenanceError(
                    "Bhavcopy ZIP contains a corrupt member."
                )
    except BadZipFile as exc:
        raise NSEBhavcopyProvenanceError(
            "Invalid NSE Bhavcopy ZIP archive."
        ) from exc

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

    audit_reasons = [
        "OFFICIAL_UDIFF_SCHEMA_MAPPING_UNVERIFIED",
        "SOURCE_AUTHENTICITY_NOT_INDEPENDENTLY_VERIFIED",
    ]

    if reconciliation["coverage_status"] != "PASS":
        audit_reasons.append(
            "MII_SYMBOL_COVERAGE_INCOMPLETE"
        )

    return {
        "source": "NSE",
        "source_format": "NSE_CM_UDIFF_ZIP",
        "source_filename": source_filename.strip(),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_size_bytes": len(source_bytes),
        "source_provenance_status": "HASH_RECORDED",
        "source_authenticity_status": "UNVERIFIED",
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
