"""Audit company-level classification with explicit source provenance.

No third-party vendor is treated as an official NSE source.
Third-party imports require an approved commercial licence reference.
Sector mapping remains disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from data.providers.nse_industry_classification import (
    load_industry_classification_file,
)
from data.providers.nse_universe import fetch_nse_equity_universe


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "nse"
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


def _clean(series: pd.Series) -> pd.Series:
    """Normalize identifiers for exact matching."""
    return series.astype("string").str.strip().str.upper()


def _source_status(data: pd.DataFrame) -> str:
    """Identify whether the NSE universe came from primary MII."""
    if "Source" not in data.columns:
        return "UNKNOWN_SOURCE"

    sources = (
        data["Source"]
        .dropna()
        .astype(str)
        .str.upper()
        .unique()
        .tolist()
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
    """Build an auditable source record and enforce vendor licensing."""

    path = Path(input_path)

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(
            f"Classification input file not found: {path}"
        )

    if source_type not in SOURCE_TYPES:
        raise ValueError(
            f"Invalid source type. Choose one of: {', '.join(SOURCE_TYPES)}"
        )

    if license_status not in LICENSE_STATUSES:
        raise ValueError(
            "Invalid license status. Choose one of: "
            + ", ".join(LICENSE_STATUSES)
        )

    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError("A source name is required.")

    if (
        not isinstance(source_reference, str)
        or not source_reference.strip()
    ):
        raise ValueError("A source URL or document reference is required.")

    if license_status == "REJECTED":
        raise PermissionError(
            "Import blocked: the source licence has been rejected."
        )

    if (
        source_type == "THIRD_PARTY_VENDOR"
        and license_status != "APPROVED"
    ):
        raise PermissionError(
            "Vendor import blocked: commercial licence status "
            "must be APPROVED."
        )

    if (
        source_type == "THIRD_PARTY_VENDOR"
        and not (
            isinstance(license_reference, str)
            and license_reference.strip()
        )
    ):
        raise ValueError(
            "Vendor import requires a licence approval reference."
        )

    if effective_date:
        try:
            date.fromisoformat(effective_date)
        except ValueError as exc:
            raise ValueError(
                "Effective date must use YYYY-MM-DD format."
            ) from exc

    file_bytes = path.read_bytes()

    return {
        "source_type": source_type,
        "source_name": source_name.strip(),
        "source_reference": source_reference.strip(),
        "downloaded_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "effective_date": effective_date or None,
        "license_status": license_status,
        "license_reference": (
            license_reference.strip()
            if isinstance(license_reference, str)
            and license_reference.strip()
            else None
        ),
        "file_name": path.name,
        "file_size_bytes": len(file_bytes),
        "file_sha256": hashlib.sha256(file_bytes).hexdigest(),
        "source_type_is_operator_declared": True,
        "note": (
            "Source type and licence status are operator-declared. "
            "The hash identifies file content but does not independently "
            "prove source authenticity or licensing."
        ),
    }


def build_industry_classification_audit(
    classification: pd.DataFrame,
    nse_universe: pd.DataFrame,
    classification_source_type: str = "NSE_OFFICIAL",
    license_status: str = "NOT_REQUIRED",
) -> tuple[pd.DataFrame, dict]:
    """Compare classification with NSE MII EQ without inferring sectors."""

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
            "Third-party vendor classification is not licensed for import."
        )

    required_classification = {
        "Symbol",
        "ISIN",
        "Sector",
        "Industry",
        "Basic Industry",
    }
    required_nse = {"Symbol", "ISIN", "Series"}

    if not required_classification.issubset(classification.columns):
        raise ValueError(
            "Classification requires Symbol, ISIN, Sector, "
            "Industry and Basic Industry."
        )

    if not required_nse.issubset(nse_universe.columns):
        raise ValueError(
            "NSE universe requires Symbol, ISIN and Series."
        )

    nse_source_status = _source_status(nse_universe)

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

    duplicate_classification = (
        classification_data["Symbol"].duplicated(keep=False)
    )

    if duplicate_classification.any():
        raise ValueError(
            "Duplicate classification symbols: "
            + ", ".join(
                classification_data.loc[
                    duplicate_classification, "Symbol"
                ].unique().tolist()
            )
        )

    nse_eq = nse_data[
        nse_data["Series"].eq("EQ")
    ].copy()

    duplicate_nse = nse_eq["Symbol"].duplicated(keep=False)

    ambiguous_symbols = set(
        nse_eq.loc[duplicate_nse, "Symbol"].dropna().tolist()
    )

    nse_unique = nse_eq[
        ~duplicate_nse
    ][["Symbol", "ISIN"]].rename(
        columns={"ISIN": "NSE_ISIN"}
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

    source_authorized = (
        classification_source_type == "NSE_OFFICIAL"
        and license_status in {"APPROVED", "NOT_REQUIRED"}
    )

    result["Classification_Source_Type"] = classification_source_type
    result["Classification_License_Status"] = license_status

    result["Approved"] = (
        result["Audit_Status"].eq("MATCH")
        & (nse_source_status == "PRIMARY_MII")
        & source_authorized
    )

    total = len(result)
    matched = int(result["Audit_Status"].eq("MATCH").sum())
    mismatches = int(
        result["Audit_Status"].eq("ISIN_MISMATCH").sum()
    )
    missing = int(
        result["Audit_Status"].eq("NSE_EQ_SYMBOL_MISSING").sum()
    )
    ambiguous = int(
        result["Audit_Status"].eq("NSE_EQ_SYMBOL_AMBIGUOUS").sum()
    )

    audit_passed = (
        total > 0
        and nse_source_status == "PRIMARY_MII"
        and matched == total
        and mismatches == 0
        and missing == 0
        and ambiguous == 0
    )

    summary = {
        "audit_id": datetime.now(
            timezone.utc
        ).strftime("%Y%m%d_%H%M%S"),
        "audit_time_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "PASS" if audit_passed else "REVIEW",
        "nse_source_status": nse_source_status,
        "classification_source_type": classification_source_type,
        "classification_license_status": license_status,
        "source_authorized_for_nse_mapping": source_authorized,
        "classification_rows": total,
        "nse_eq_matched": matched,
        "isin_mismatches": mismatches,
        "nse_eq_missing": missing,
        "ambiguous_nse_symbols": ambiguous,
        "approved_rows": int(result["Approved"].sum()),
        "mapping_eligible": bool(
            audit_passed
            and source_authorized
            and int(result["Approved"].sum()) == total
        ),
        "sector_mapping_activated": False,
    }

    return (
        result.sort_values("Symbol").reset_index(drop=True),
        summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit company-level classification with source "
            "provenance and licensing controls."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Classification CSV or XLSX file.",
    )
    parser.add_argument(
        "--source-type",
        required=True,
        choices=SOURCE_TYPES,
        help="Declared source authority.",
    )
    parser.add_argument(
        "--source-name",
        required=True,
        help="Name of the source or vendor.",
    )
    parser.add_argument(
        "--source-reference",
        required=True,
        help="Official URL, vendor document, or source reference.",
    )
    parser.add_argument(
        "--license-status",
        required=True,
        choices=LICENSE_STATUSES,
        help="Explicit licence review status.",
    )
    parser.add_argument(
        "--license-reference",
        default=None,
        help="Contract, approval email, or licence document reference.",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        help="Classification effective date in YYYY-MM-DD format.",
    )

    args = parser.parse_args()

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
        source_reference=args.source_reference,
        as_of_date=args.as_of_date,
    )

    print("Downloading NSE MII security master...")

    nse_universe = fetch_nse_equity_universe()

    detail, summary = build_industry_classification_audit(
        classification=classification,
        nse_universe=nse_universe,
        classification_source_type=args.source_type,
        license_status=args.license_status,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    detail_path = (
        REPORT_DIR / "nse_industry_classification_audit.csv"
    )
    summary_path = (
        REPORT_DIR / "nse_industry_classification_summary.json"
    )
    provenance_path = (
        REPORT_DIR / "classification_source_provenance.json"
    )

    detail.to_csv(detail_path, index=False)

    summary["source_provenance"] = provenance

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    provenance_path.write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n========== INDUSTRY CLASSIFICATION AUDIT ==========")

    for key, value in summary.items():
        if key != "source_provenance":
            print(f"{key}: {value}")

    print("\nDetail:", detail_path)
    print("Summary:", summary_path)
    print("Provenance:", provenance_path)

    if summary["status"] != "PASS":
        raise SystemExit(
            "AUDIT REVIEW: NSE MII reconciliation requires review."
        )

    if not summary["mapping_eligible"]:
        raise SystemExit(
            "AUDIT PASS, BUT SOURCE IS NOT AUTHORIZED "
            "FOR NSE PRODUCTION MAPPING."
        )

    print("\nAUDIT PASS: source and NSE MII reconciliation passed.")
    print("Sector Mapping remains disabled.")


if __name__ == "__main__":
    main()