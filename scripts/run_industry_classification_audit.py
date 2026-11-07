
"""Audit full NSE EQ classification coverage with provenance and taxonomy gates.

Production NSE sector mapping remains disabled until source authenticity
and authorization are independently verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from data.providers.classification_taxonomy_validator import (
    validate_classification_taxonomy,
)
from data.providers.nse_industry_classification import (
    load_industry_classification_file,
)
from data.providers.nse_universe import fetch_nse_equity_universe


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    PROJECT_ROOT / "data" / "raw" / "nse"
    / "industry_classification.csv"
)
REPORT_DIR = PROJECT_ROOT / "reports" / "industry_classification"

SOURCE_TYPES = (
    "NSE_OFFICIAL",
    "BSE_OFFICIAL",
    "THIRD_PARTY_VENDOR",
)
LICENSE_STATUSES = (
    "PENDING",
    "APPROVED",
    "NOT_REQUIRED",
    "REJECTED",
)
SOURCE_AUTHENTICITY_UNVERIFIED = "UNVERIFIED"


def _clean(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.upper()
    return cleaned.replace("", pd.NA)


def _source_status(data: pd.DataFrame) -> str:
    if "Source" not in data.columns:
        return "UNKNOWN_SOURCE"

    sources = (
        data["Source"].dropna().astype(str).str.upper().unique().tolist()
    )

    if sources and all("MII" in source for source in sources):
        return "PRIMARY_MII"

    if any(
        "LEGACY" in source or "EQUITY MASTER" in source
        for source in sources
    ):
        return "LEGACY_FALLBACK"

    return "UNKNOWN_SOURCE"


def build_source_provenance(
    input_path: str | Path,
    source_type: str,
    source_name: str,
    source_reference: str,
    license_status: str,
    license_reference: str | None = None,
    effective_date: str | None = None,
) -> dict:
    path = Path(input_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"Classification input file not found: {path}"
        )

    if source_type not in SOURCE_TYPES:
        raise ValueError("Invalid source type.")

    if license_status not in LICENSE_STATUSES:
        raise ValueError("Invalid license status.")

    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("A source name is required.")

    if (
        not isinstance(source_reference, str)
        or not source_reference.strip()
    ):
        raise ValueError("A source reference is required.")

    if license_status == "REJECTED":
        raise PermissionError("The source licence has been rejected.")

    if (
        source_type == "THIRD_PARTY_VENDOR"
        and license_status != "APPROVED"
    ):
        raise PermissionError(
            "Vendor import blocked: licence status must be APPROVED."
        )

    if (
        source_type == "THIRD_PARTY_VENDOR"
        and not (
            isinstance(license_reference, str)
            and license_reference.strip()
        )
    ):
        raise ValueError("Vendor licence approval reference is required.")

    if effective_date:
        try:
            date.fromisoformat(effective_date)
        except ValueError as exc:
            raise ValueError(
                "Effective date must use YYYY-MM-DD format."
            ) from exc

    content = path.read_bytes()

    return {
        "source_type": source_type,
        "source_name": source_name.strip(),
        "source_reference": source_reference.strip(),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "effective_date": effective_date or None,
        "license_status": license_status,
        "license_reference": (
            license_reference.strip()
            if isinstance(license_reference, str)
            and license_reference.strip()
            else None
        ),
        "file_name": path.name,
        "file_size_bytes": len(content),
        "file_sha256": hashlib.sha256(content).hexdigest(),
        "source_type_is_operator_declared": True,
        "source_authenticity_status": SOURCE_AUTHENTICITY_UNVERIFIED,
        "source_authenticity_verified": False,
        "source_authorized_for_nse_mapping": False,
        "note": (
            "Operator-declared source details and file hashes do not "
            "prove origin, authenticity or licensing. Production NSE "
            "mapping authorization remains blocked."
        ),
    }


def build_taxonomy_provenance(
    input_path: str | Path,
    source_reference: str,
) -> dict:
    path = Path(input_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"Official taxonomy reference not found: {path}"
        )

    if path.suffix.lower() != ".csv":
        raise ValueError("Taxonomy reference must be a CSV file.")

    if (
        not isinstance(source_reference, str)
        or not source_reference.strip()
    ):
        raise ValueError("Taxonomy source reference is required.")

    content = path.read_bytes()

    if not content:
        raise ValueError("Taxonomy reference file is empty.")

    return {
        "file_name": path.name,
        "file_sha256": hashlib.sha256(content).hexdigest(),
        "file_size_bytes": len(content),
        "source_reference": source_reference.strip(),
        "source_reference_is_operator_declared": True,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "note": (
            "The source reference is operator-declared. File hash "
            "does not prove official origin, authenticity or licensing."
        ),
    }


def _load_taxonomy_file(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)

    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(
            f"Official taxonomy reference not found: {file_path}"
        )

    if file_path.suffix.lower() != ".csv":
        raise ValueError("Taxonomy reference must be a CSV file.")

    return pd.read_csv(
        file_path,
        dtype="string",
        encoding="utf-8-sig",
        low_memory=False,
    )


def _missing_classification_rows(
    nse_eq: pd.DataFrame,
    classification_symbols: set,
    classification_columns: list[str],
) -> pd.DataFrame:
    missing = nse_eq.loc[
        ~nse_eq["Symbol"].isin(classification_symbols)
    ].copy()

    if missing.empty:
        return pd.DataFrame()

    rows = []

    for _, nse_row in missing.iterrows():
        row = {column: pd.NA for column in classification_columns}

        row["Symbol"] = nse_row["Symbol"]
        row["ISIN"] = nse_row["ISIN"]
        row["NSE_ISIN"] = nse_row["ISIN"]
        row["NSE_Source"] = nse_row.get("Source", pd.NA)
        row["Audit_Status"] = "CLASSIFICATION_MISSING"
        row["Taxonomy_Status"] = "NOT_AVAILABLE"
        row["Taxonomy_Validated"] = False
        row["Classification_Source_Type"] = pd.NA
        row["Classification_License_Status"] = pd.NA
        row["Source_Authenticity_Status"] = (
            SOURCE_AUTHENTICITY_UNVERIFIED
        )
        row["Source_Authenticity_Verified"] = False
        row["Approved"] = False

        rows.append(row)

    return pd.DataFrame(rows)


def build_industry_classification_audit(
    classification: pd.DataFrame,
    nse_universe: pd.DataFrame,
    classification_source_type: str = "NSE_OFFICIAL",
    license_status: str = "NOT_REQUIRED",
    official_taxonomy: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:

    if not isinstance(classification, pd.DataFrame) or classification.empty:
        raise ValueError("Industry classification data is empty.")

    if not isinstance(nse_universe, pd.DataFrame) or nse_universe.empty:
        raise ValueError("NSE universe data is empty.")

    if classification_source_type not in SOURCE_TYPES:
        raise ValueError("Invalid classification source type.")

    if license_status not in LICENSE_STATUSES:
        raise ValueError("Invalid classification licence status.")

    if license_status == "REJECTED":
        raise PermissionError("Classification source licence is rejected.")

    if (
        classification_source_type == "THIRD_PARTY_VENDOR"
        and license_status != "APPROVED"
    ):
        raise PermissionError(
            "Third-party vendor classification is not licensed."
        )

    required_classification = {
        "Symbol", "ISIN", "Sector", "Industry", "Basic Industry",
    }
    required_nse = {"Symbol", "ISIN", "Series"}

    if not required_classification.issubset(classification.columns):
        raise ValueError(
            "Classification requires Symbol, ISIN, Sector, "
            "Industry and Basic Industry."
        )

    if not required_nse.issubset(nse_universe.columns):
        raise ValueError("NSE universe requires Symbol, ISIN and Series.")

    classification_data = classification.copy()
    nse_data = nse_universe.copy()

    classification_data["Symbol"] = _clean(
        classification_data["Symbol"]
    )
    classification_data["ISIN"] = _clean(
        classification_data["ISIN"]
    )
    nse_data["Symbol"] = _clean(nse_data["Symbol"])
    nse_data["ISIN"] = _clean(nse_data["ISIN"])
    nse_data["Series"] = _clean(nse_data["Series"])

    if classification_data["Symbol"].isna().any():
        raise ValueError("Classification contains missing symbols.")

    if classification_data["ISIN"].isna().any():
        raise ValueError("Classification contains missing ISIN values.")

    duplicate_classification_symbol = (
        classification_data["Symbol"].duplicated(keep=False)
    )

    if duplicate_classification_symbol.any():
        duplicates = classification_data.loc[
            duplicate_classification_symbol, "Symbol"
        ].unique().tolist()
        raise ValueError(
            "Duplicate classification symbols: " + ", ".join(duplicates)
        )

    nse_source_status = _source_status(nse_data)

    nse_eq = nse_data.loc[nse_data["Series"].eq("EQ")].copy()

    if nse_eq.empty:
        raise ValueError("NSE universe contains no EQ series records.")

    nse_eq_total = len(nse_eq)

    invalid_nse_identity = (
        nse_eq["Symbol"].isna() | nse_eq["ISIN"].isna()
    )
    nse_eq_invalid_identity_rows = int(invalid_nse_identity.sum())

    duplicate_nse_symbol = nse_eq["Symbol"].duplicated(keep=False)
    ambiguous_symbols = set(
        nse_eq.loc[duplicate_nse_symbol, "Symbol"].dropna().tolist()
    )

    duplicate_nse_isin = nse_eq["ISIN"].duplicated(keep=False)
    duplicate_nse_isin_values = set(
        nse_eq.loc[duplicate_nse_isin, "ISIN"].dropna().tolist()
    )
    duplicate_nse_isin_rows = int(duplicate_nse_isin.sum())

    duplicate_classification_isin = (
        classification_data["ISIN"].duplicated(keep=False)
    )
    duplicate_classification_isin_rows = int(
        duplicate_classification_isin.sum()
    )

    # Taxonomy validation applies only to supplied classification rows.
    if official_taxonomy is None:
        classification_data["Taxonomy_Status"] = (
            "TAXONOMY_REFERENCE_NOT_PROVIDED"
        )
        classification_data["Taxonomy_Validated"] = False

        taxonomy_summary = {
            "status": "REVIEW",
            "classification_rows": len(classification_data),
            "taxonomy_matched_rows": 0,
            "missing_hierarchy_rows": 0,
            "unknown_hierarchy_rows": 0,
            "official_taxonomy_paths": 0,
            "matching_method": "NOT_RUN",
            "reason": "Official taxonomy reference was not provided.",
        }
    else:
        classification_data, taxonomy_summary = (
            validate_classification_taxonomy(
                classification=classification_data,
                official_taxonomy=official_taxonomy,
            )
        )

    classification_columns = list(classification_data.columns)
    classification_symbols = set(
        classification_data["Symbol"].dropna().tolist()
    )

    # Forward reconciliation: classification -> NSE EQ.
    nse_unique = nse_eq.loc[
        ~duplicate_nse_symbol & ~invalid_nse_identity
    ].copy()

    nse_unique = nse_unique[
        ["Symbol", "ISIN"]
        + (["Source"] if "Source" in nse_unique.columns else [])
    ].rename(
        columns={
            "ISIN": "NSE_ISIN",
            "Source": "NSE_Source",
        }
    )

    result = classification_data.merge(
        nse_unique,
        on="Symbol",
        how="left",
        validate="one_to_one",
    )

    symbol_missing = result["NSE_ISIN"].isna()

    isin_match = (
        result["ISIN"].notna()
        & result["NSE_ISIN"].notna()
        & result["ISIN"].eq(result["NSE_ISIN"])
    )

    result["Audit_Status"] = "ISIN_MISMATCH"
    result.loc[isin_match, "Audit_Status"] = "MATCH"

    result.loc[
        symbol_missing, "Audit_Status"
    ] = "NSE_EQ_SYMBOL_MISSING"

    result.loc[
        result["Symbol"].isin(ambiguous_symbols),
        "Audit_Status",
    ] = "NSE_EQ_SYMBOL_AMBIGUOUS"

    result.loc[
        result["ISIN"].isin(duplicate_nse_isin_values),
        "Audit_Status",
    ] = "NSE_EQ_ISIN_DUPLICATE"

    # Reverse reconciliation: NSE EQ -> classification.
    reverse_missing = _missing_classification_rows(
        nse_eq=nse_eq,
        classification_symbols=classification_symbols,
        classification_columns=classification_columns,
    )

    if not reverse_missing.empty:
        result = pd.concat(
            [result, reverse_missing],
            ignore_index=True,
            sort=False,
        )

    # Authenticity is deliberately not inferred from operator labels.
    source_authenticity_status = SOURCE_AUTHENTICITY_UNVERIFIED
    source_authenticity_verified = False
    source_authorized = False

    result["Classification_Source_Type"] = result.get(
        "Classification_Source_Type", classification_source_type
    )
    result["Classification_License_Status"] = result.get(
        "Classification_License_Status", license_status
    )
    result["Source_Authenticity_Status"] = (
        source_authenticity_status
    )
    result["Source_Authenticity_Verified"] = (
        source_authenticity_verified
    )

    result["Approved"] = False

    matched = int(result["Audit_Status"].eq("MATCH").sum())
    mismatches = int(
        result["Audit_Status"].eq("ISIN_MISMATCH").sum()
    )
    classification_symbols_missing_from_nse = int(
        result["Audit_Status"].eq("NSE_EQ_SYMBOL_MISSING").sum()
    )
    ambiguous = int(
        result["Audit_Status"].eq("NSE_EQ_SYMBOL_AMBIGUOUS").sum()
    )
    classification_missing = int(
        result["Audit_Status"].eq("CLASSIFICATION_MISSING").sum()
    )

    taxonomy_matched = int(
        classification_data["Taxonomy_Validated"].fillna(False).sum()
    )

    classification_only_symbols = (
        classification_symbols_missing_from_nse
    )

    # Coverage denominator is the complete NSE EQ universe.
    nse_eq_coverage_pct = round(
        (matched / nse_eq_total) * 100,
        4,
    )

    full_universe_coverage_passed = bool(
        matched == nse_eq_total
        and classification_missing == 0
        and mismatches == 0
        and classification_only_symbols == 0
        and ambiguous == 0
        and nse_eq_invalid_identity_rows == 0
        and duplicate_nse_isin_rows == 0
        and duplicate_classification_isin_rows == 0
        and len(classification_data) == nse_eq_total
        and nse_source_status == "PRIMARY_MII"
    )

    identity_audit_passed = full_universe_coverage_passed

    taxonomy_passed = bool(
        taxonomy_summary["status"] == "PASS"
        and taxonomy_matched == len(classification_data)
    )

    summary = {
        "audit_id": datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        ),
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if identity_audit_passed else "REVIEW",
        "nse_source_status": nse_source_status,
        "classification_source_type": classification_source_type,
        "classification_license_status": license_status,
        "source_authenticity_status": source_authenticity_status,
        "source_authenticity_verified": source_authenticity_verified,
        "source_authenticity_reason": (
            "No trusted independent source-authenticity verifier "
            "is implemented. Operator-declared labels and file hashes "
            "cannot authorize production NSE mapping."
        ),
        "source_authorized_for_nse_mapping": source_authorized,
        "classification_rows": len(classification_data),
        "nse_eq_universe_rows": nse_eq_total,
        "nse_eq_matched": matched,
        "nse_eq_coverage_pct": nse_eq_coverage_pct,
        "full_universe_coverage_passed": (
            full_universe_coverage_passed
        ),
        "nse_eq_missing_classification": classification_missing,
        "classification_symbols_missing_from_nse": (
            classification_symbols_missing_from_nse
        ),
        "nse_eq_invalid_identity_rows": (
            nse_eq_invalid_identity_rows
        ),
        "duplicate_nse_isin_rows": duplicate_nse_isin_rows,
        "duplicate_classification_isin_rows": (
            duplicate_classification_isin_rows
        ),
        "isin_mismatches": mismatches,
        "nse_eq_missing": classification_symbols_missing_from_nse,
        "ambiguous_nse_symbols": ambiguous,
        "taxonomy_status": "PASS" if taxonomy_passed else "REVIEW",
        "taxonomy_matched_rows": taxonomy_matched,
        "taxonomy_unmatched_rows": (
            len(classification_data) - taxonomy_matched
        ),
        "taxonomy_summary": taxonomy_summary,
        "approved_rows": 0,
        "mapping_eligible": False,
        "sector_mapping_activated": False,
    }

    return (
        result.sort_values(
            ["Symbol", "Audit_Status"],
            na_position="last",
        ).reset_index(drop=True),
        summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit full NSE EQ classification coverage with source, "
            "licensing, MII, taxonomy and authenticity gates."
        )
    )

    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--source-type", required=True, choices=SOURCE_TYPES
    )
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-reference", required=True)
    parser.add_argument(
        "--license-status", required=True, choices=LICENSE_STATUSES
    )
    parser.add_argument("--license-reference", default=None)
    parser.add_argument("--as-of-date", default=None)
    parser.add_argument("--taxonomy-input", type=Path, default=None)
    parser.add_argument(
        "--taxonomy-source-reference",
        default=None,
        help="Operator-declared source reference for taxonomy.",
    )

    args = parser.parse_args()

    if (
        args.taxonomy_input is not None
        and not args.taxonomy_source_reference
    ):
        parser.error(
            "--taxonomy-source-reference is required when "
            "--taxonomy-input is supplied."
        )

    if (
        args.taxonomy_input is None
        and args.taxonomy_source_reference
    ):
        parser.error(
            "--taxonomy-source-reference cannot be used without "
            "--taxonomy-input."
        )

    provenance = build_source_provenance(
        input_path=args.input,
        source_type=args.source_type,
        source_name=args.source_name,
        source_reference=args.source_reference,
        license_status=args.license_status,
        license_reference=args.license_reference,
        effective_date=args.as_of_date,
    )

    classification = load_industry_classification_file(
        file_path=args.input,
        source_name=args.source_name,
        source_reference=args.source_refe