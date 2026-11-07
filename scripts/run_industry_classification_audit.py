"""Audit official NSE industry classification against NSE MII EQ.

This audit does not activate sector membership.
Only exact Symbol + ISIN matches from the primary NSE MII
security master can receive MATCH status.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
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


def _clean(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper()


def _source_status(data: pd.DataFrame) -> str:
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

    if any("LEGACY" in source or "EQUITY MASTER" in source
           for source in sources):
        return "LEGACY_FALLBACK"

    return "UNKNOWN_SOURCE"


def build_industry_classification_audit(
    classification: pd.DataFrame,
    nse_universe: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Compare official classification with NSE MII EQ records."""

    if not isinstance(classification, pd.DataFrame) or classification.empty:
        raise ValueError("Industry classification data is empty.")

    if not isinstance(nse_universe, pd.DataFrame) or nse_universe.empty:
        raise ValueError("NSE universe data is empty.")

    required_classification = {
        "Symbol", "ISIN", "Sector", "Industry", "Basic Industry"
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

    source_status = _source_status(nse_universe)

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
    result.loc[symbol_missing, "Audit_Status"] = "NSE_EQ_SYMBOL_MISSING"

    result.loc[
        result["Symbol"].isin(ambiguous_symbols),
        "Audit_Status",
    ] = "NSE_EQ_SYMBOL_AMBIGUOUS"

    result["Approved"] = (
        result["Audit_Status"].eq("MATCH")
        & (source_status == "PRIMARY_MII")
    )

    total = len(result)
    matched = int(result["Audit_Status"].eq("MATCH").sum())

    mismatches = int(
        result["Audit_Status"].eq("ISIN_MISMATCH").sum()
    )

    missing = int(
        result["Audit_Status"].eq(
            "NSE_EQ_SYMBOL_MISSING"
        ).sum()
    )

    ambiguous = int(
        result["Audit_Status"].eq(
            "NSE_EQ_SYMBOL_AMBIGUOUS"
        ).sum()
    )

    passed = (
        total > 0
        and source_status == "PRIMARY_MII"
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
        "status": "PASS" if passed else "REVIEW",
        "nse_source_status": source_status,
        "classification_rows": total,
        "nse_eq_matched": matched,
        "isin_mismatches": mismatches,
        "nse_eq_missing": missing,
        "ambiguous_nse_symbols": ambiguous,
        "approved_rows": int(result["Approved"].sum()),
        "sector_mapping_activated": False,
    }

    return (
        result.sort_values("Symbol").reset_index(drop=True),
        summary,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Audit NSE industry classification against MII."
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Official NSE classification CSV or XLSX file.",
    )

    parser.add_argument(
        "--as-of-date",
        default=None,
        help="Classification effective date.",
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(
            f"Official classification file not found: {args.input}"
        )

    classification = load_industry_classification_file(
        file_path=args.input,
        source_name="NSE Official Industry Classification",
        source_reference="Official NSE classification document",
        as_of_date=args.as_of_date,
    )

    print("Downloading NSE MII security master...")

    nse_universe = fetch_nse_equity_universe()

    detail, summary = build_industry_classification_audit(
        classification,
        nse_universe,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    detail_path = (
        REPORT_DIR / "nse_industry_classification_audit.csv"
    )

    summary_path = (
        REPORT_DIR / "nse_industry_classification_summary.json"
    )

    detail.to_csv(detail_path, index=False)

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n========== INDUSTRY CLASSIFICATION AUDIT ==========")

    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\nDetail:", detail_path)
    print("Summary:", summary_path)

    if summary["status"] != "PASS":
        raise SystemExit(
            "AUDIT REVIEW: Industry classification is not approved."
        )

    print("\nAUDIT PASS: NSE MII reconciliation successful.")
    print("Sector Mapping remains disabled.")


if __name__ == "__main__":
    main()
  
