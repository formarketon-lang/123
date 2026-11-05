
"""Live audit of Nifty FMCG constituents against NSE MII EQ universe."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data.providers.nifty_constituents import fetch_sector_constituents
from data.providers.nse_universe import fetch_nse_equity_universe

REPORT_DIR = Path("reports/sector_constituents")
SECTOR = "FMCG"


def build_constituent_audit(constituents, nse_universe, sector=SECTOR):
    required_constituent = {"Symbol", "ISIN"}
    required_nse = {"Symbol", "ISIN", "Series"}

    if not required_constituent.issubset(constituents.columns):
        raise ValueError("Constituent data must contain Symbol and ISIN.")

    if not required_nse.issubset(nse_universe.columns):
        raise ValueError("NSE universe must contain Symbol, ISIN and Series.")

    sector_data = constituents.copy()
    nse_data = nse_universe.copy()

    for frame in (sector_data, nse_data):
        frame["Symbol"] = (
            frame["Symbol"].astype("string").str.strip().str.upper()
        )
        frame["ISIN"] = (
            frame["ISIN"].astype("string").str.strip().str.upper()
        )

    sector_data = sector_data[
        sector_data["Symbol"].notna() & sector_data["Symbol"].ne("")
    ].copy()

    nse_data = nse_data[
        nse_data["Series"].astype("string").str.strip().str.upper().eq("EQ")
        & nse_data["Symbol"].notna()
        & nse_data["Symbol"].ne("")
    ].copy()

    sector_duplicates = int(
        sector_data["Symbol"].duplicated(keep=False).sum()
    )
    nse_duplicates = int(
        nse_data["Symbol"].duplicated(keep=False).sum()
    )

    # Ambiguous duplicate NSE symbols are not approved.
    nse_unique = nse_data.drop_duplicates(
        subset=["Symbol"], keep=False
    ).rename(columns={"ISIN": "NSE_ISIN"})

    audit = sector_data.merge(
        nse_unique[["Symbol", "NSE_ISIN"]],
        on="Symbol",
        how="left",
        validate="many_to_one",
    )

    audit["NSE_EQ_Match"] = audit["NSE_ISIN"].notna()
    audit["ISIN_Status"] = "NSE_SYMBOL_MISSING"

    both_isins = audit["ISIN"].notna() & audit["NSE_ISIN"].notna()

    audit.loc[
        both_isins & audit["ISIN"].eq(audit["NSE_ISIN"]),
        "ISIN_Status",
    ] = "MATCH"

    audit.loc[
        both_isins & audit["ISIN"].ne(audit["NSE_ISIN"]),
        "ISIN_Status",
    ] = "MISMATCH"

    audit.loc[
        audit["NSE_ISIN"].notna() & audit["ISIN"].isna(),
        "ISIN_Status",
    ] = "CONSTITUENT_ISIN_MISSING"

    audit["Audit_Status"] = "SYMBOL_MATCH_ISIN_MATCH"

    audit.loc[
        ~audit["NSE_EQ_Match"], "Audit_Status"
    ] = "NSE_EQ_SYMBOL_MISSING"

    audit.loc[
        audit["ISIN_Status"].eq("MISMATCH"), "Audit_Status"
    ] = "ISIN_MISMATCH"

    audit.loc[
        audit["ISIN_Status"].eq("CONSTITUENT_ISIN_MISSING"),
        "Audit_Status",
    ] = "CONSTITUENT_ISIN_MISSING"

    total = len(audit)
    matched = int(audit["NSE_EQ_Match"].sum())
    missing = total - matched
    isin_mismatch = int(audit["ISIN_Status"].eq("MISMATCH").sum())
    isin_match = int(audit["ISIN_Status"].eq("MATCH").sum())
    isin_missing = int(
        audit["ISIN_Status"].eq("CONSTITUENT_ISIN_MISSING").sum()
    )

    status = (
        "PASS"
        if total > 0
        and missing == 0
        and isin_mismatch == 0
        and isin_missing == 0
        and sector_duplicates == 0
        and nse_duplicates == 0
        else "REVIEW"
    )

    summary = {
        "sector": sector,
        "index": f"Nifty {sector}",
        "source": "NSE Indices Official Constituents",
        "nse_source": "NSE MII Security Master",
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_constituents": total,
        "nse_eq_matched": matched,
        "nse_eq_missing": missing,
        "isin_matched": isin_match,
        "isin_mismatches": isin_mismatch,
        "constituent_isin_missing": isin_missing,
        "duplicate_constituent_symbol_rows": sector_duplicates,
        "duplicate_nse_eq_symbol_rows": nse_duplicates,
        "approved_for_sector_membership": status == "PASS",
    }

    return audit.sort_values("Symbol").reset_index(drop=True), summary


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("Downloading official Nifty FMCG constituents...")
    constituents = fetch_sector_constituents(SECTOR)
    print("Constituents:", len(constituents))

    print("Downloading NSE MII EQ universe...")
    nse_universe = fetch_nse_equity_universe()
    print("NSE EQ rows:", len(nse_universe))

    detail, summary = build_constituent_audit(
        constituents, nse_universe, SECTOR
    )

    detail_path = REPORT_DIR / "fmcg_constituents_vs_nse_eq.csv"
    summary_path = REPORT_DIR / "fmcg_constituents_audit.json"

    detail.to_csv(detail_path, index=False)

    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n========== FMCG CONSTITUENTS AUDIT ==========")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print("Detail report:", detail_path)
    print("Summary report:", summary_path)


if __name__ == "__main__":
    main()
  
