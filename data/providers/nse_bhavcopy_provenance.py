"""Provenance and coverage audit for NSE CM-UDiFF Bhavcopy."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile

import pandas as pd

from data.providers.nse_bhavcopy_mii_validation import (
    reconcile_bhavcopy_with_mii,
)


class NSEBhavcopyProvenanceError(ValueError):
    """Raised when NSE Bhavcopy provenance cannot be established."""


NSE_OFFICIAL_ARCHIVE_HOST = "nsearchives.nseindia.com"
NSE_UDIFF_SCHEMA_REFERENCE_URL = (
    "https://www.nseindia.com/static/resources/forms-formats-members"
)


def _validate_bhavcopy_archive(source_bytes: bytes) -> None:
    """Validate ZIP integrity and require exactly one safe CSV member."""

    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise NSEBhavcopyProvenanceError(
            "Original NSE Bhavcopy archive bytes are required."
        )

    try:
        with ZipFile(BytesIO(source_bytes)) as archive:
            members = [
                item for item in archive.infolist()
                if not item.is_dir()
            ]

            if archive.testzip() is not None:
                raise NSEBhavcopyProvenanceError(
                    "Bhavcopy ZIP contains a corrupt member."
                )

            csv_members = []

            for item in members:
                path = PurePosixPath(item.filename)

                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in item.filename
                ):
                    raise NSEBhavcopyProvenanceError(
                        "Unsafe path found inside Bhavcopy ZIP."
                    )

                if item.filename.lower().endswith(".csv"):
                    csv_members.append(item)

            if len(csv_members) != 1:
                raise NSEBhavcopyProvenanceError(
                    "Expected exactly one CSV in Bhavcopy ZIP; "
                    f"found {len(csv_members)}."
                )

            if csv_members[0].file_size == 0:
                raise NSEBhavcopyProvenanceError(
                    "Bhavcopy CSV inside ZIP is empty."
                )

    except BadZipFile as exc:
        raise NSEBhavcopyProvenanceError(
            "Invalid NSE Bhavcopy ZIP archive."
        ) from exc


def audit_nse_bhavcopy_provenance(
    bhavcopy: pd.DataFrame,
    universe: pd.DataFrame,
    source_bytes: bytes,
    source_filename: str,
    source_url: str | None = None,
    schema_reference_url: str | None = None,
    schema_mapping_verified: bool = False,
) -> dict:
    """Audit archive structure, hash, MII identity and coverage.

    A valid ZIP and recorded hash do not prove NSE authenticity.
    Official UDiFF schema mapping remains independently unverified.
    """

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

    _validate_bhavcopy_archive(source_bytes)

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

    parsed_source_url = urlparse(source_url or "")
    official_endpoint = (
        parsed_source_url.scheme == "https"
        and parsed_source_url.hostname == NSE_OFFICIAL_ARCHIVE_HOST
    )
    official_schema_reference = (
        schema_reference_url == NSE_UDIFF_SCHEMA_REFERENCE_URL
    )

    raw_schema_verified = False
    raw_schema_error = None
    if schema_mapping_verified:
        try:
            from data.providers.nse_udiff_downloader import (
                REQUIRED_RAW_FIELDS,
            )
            from data.providers.nse_udiff_bhavcopy import (
                read_nse_udiff_bhavcopy,
            )

            raw_frame = read_nse_udiff_bhavcopy(source_bytes)
            raw_schema_verified = REQUIRED_RAW_FIELDS.issubset(
                raw_frame.columns
            )
            if not raw_schema_verified:
                raw_schema_error = (
                    "Live raw header does not contain every approved "
                    "NSE UDiFF field."
                )
        except Exception as exc:
            raw_schema_error = f"{type(exc).__name__}: {exc}"

    audit_reasons = []

    if not official_endpoint:
        audit_reasons.append("OFFICIAL_NSE_HTTPS_ENDPOINT_NOT_VERIFIED")

    if not official_schema_reference:
        audit_reasons.append("OFFICIAL_UDIFF_SCHEMA_REFERENCE_NOT_RECORDED")

    if not schema_mapping_verified:
        audit_reasons.append("OFFICIAL_UDIFF_SCHEMA_CONTENT_REVIEW_PENDING")
    elif not raw_schema_verified:
        audit_reasons.append("LIVE_RAW_UDIFF_FIELDS_DO_NOT_MATCH_APPROVED_SCHEMA")

    if reconciliation["coverage_status"] != "PASS":
        audit_reasons.append(
            "MII_SYMBOL_COVERAGE_INCOMPLETE"
        )

    if reconciliation.get("unknown_count", 0):
        audit_reasons.append(
            "BHAVCOPY_SYMBOLS_NOT_PRESENT_IN_DATED_MII"
        )

    if reconciliation.get("isin_mismatch_count", 0):
        audit_reasons.append(
            "BHAVCOPY_SYMBOL_ISIN_MISMATCH"
        )

    if reconciliation.get("instrument_id_mismatch_count", 0):
        audit_reasons.append(
            "BHAVCOPY_SYMBOL_INSTRUMENT_ID_MISMATCH"
        )

    return {
        "source": "NSE",
        "source_format": "NSE_CM_UDIFF_ZIP",
        "source_filename": source_filename.strip(),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_size_bytes": len(source_bytes),
        "archive_structure_status": "PASS",
        "source_provenance_status": "HASH_RECORDED",
        "source_url": source_url or "",
        "source_authenticity_status": (
            "OFFICIAL_NSE_HTTPS_HOST"
            if official_endpoint
            else "UNVERIFIED"
        ),
        "schema_reference_url": schema_reference_url or "",
        "observation_date": reconciliation["observation_date"],
        "mii_snapshot_date": reconciliation["mii_snapshot_date"],
        "raw_observation_rows": len(bhavcopy),
        "observed_symbols": reconciliation["observed_symbols"],
        "raw_observed_symbols": reconciliation.get(
            "raw_observed_symbols",
            reconciliation["observed_symbols"],
        ),
        "expected_symbols": reconciliation["expected_symbols"],
        "unknown_symbols": reconciliation.get("unknown_symbols", []),
        "unknown_count": reconciliation.get("unknown_count", 0),
        "isin_mismatch_symbols": reconciliation.get(
            "isin_mismatch_symbols",
            [],
        ),
        "isin_mismatch_count": reconciliation.get(
            "isin_mismatch_count",
            0,
        ),
        "instrument_id_mismatch_symbols": reconciliation.get(
            "instrument_id_mismatch_symbols",
            [],
        ),
        "instrument_id_mismatch_count": reconciliation.get(
            "instrument_id_mismatch_count",
            0,
        ),
        "identity_exceptions": reconciliation.get(
            "identity_exceptions",
            [],
        ),
        "missing_symbols": reconciliation["missing_symbols"],
        "missing_count": reconciliation["missing_count"],
        "coverage_pct": reconciliation["coverage_pct"],
        "identity_status": reconciliation["identity_status"],
        "coverage_status": reconciliation["coverage_status"],
        "raw_schema_status": (
            "PASS" if raw_schema_verified else "REVIEW"
        ),
        "raw_schema_error": raw_schema_error,
        "schema_mapping_status": (
            "PASS"
            if (
                official_schema_reference
                and schema_mapping_verified
                and raw_schema_verified
            )
            else (
                "REVIEW_REFERENCE_RECORDED"
                if official_schema_reference
                else "UNVERIFIED"
            )
        ),
        "audit_status": (
            "PASS" if not audit_reasons else "REVIEW"
        ),
        "audit_reasons": audit_reasons,
    }