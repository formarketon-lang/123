
"""Official sector constituent audit against the NSE EQ universe."""

from datetime import datetime, timezone

import pandas as pd


SECTOR = "FMCG"


def _clean_text(series):
    return series.astype("string").str.strip().str.upper()


def _source_classification(nse_data):
    if "Source" not in nse_data.columns:
        return "UNKNOWN_SOURCE", "Unknown NSE source"

    sources = (
        nse_data["Source"]
        .dropna()
        .astype("string")
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    source_text = " | ".join(str(x) for x in sources)

    if sources and all("MII" in str(x).upper() for x in sources):
        return "PRIMARY_MII", source_text

    if any(
        "LEGACY" in str(x).upper()
        or "EQUITY MASTER" in str(x).upper()
        for x in sources
    ):
        return "LEGACY_FALLBACK", source_text

    return "UNKNOWN_SOURCE", source_text or "Unknown NSE source"


def build_constituent_audit(
    constituents,
    nse_universe,
    sector=SECTOR,
):
    required_constituent = {"Symbol", "ISIN"}
    required_nse = {"Symbol", "ISIN", "Series"}

    if not isinstance(constituents, pd.DataFrame) or constituents.empty:
        raise ValueError("Constituent data is empty or invalid.")

    if not isinstance(nse_universe, pd.DataFrame) or nse_universe.empty:
        raise ValueError("NSE universe is empty or invalid.")

    if not required_constituent.issubset(constituents.columns):
        raise ValueError("Constituent data must contain Symbol and ISIN.")

    if not required_nse.issubset(nse_universe.columns):
        raise ValueError("NSE universe must contain Symbol, ISIN and Series.")

    sector_data = constituents.copy()
    nse_data = nse_universe.copy()

    raw_constituent_rows = len(sector_data)
    raw_nse_rows_received = len(nse_data)

    sector_data["Symbol"] = _clean_text(sector_data["Symbol"])
    sector_data["ISIN"] = _clean_text(sector_data["ISIN"])

    nse_data["Symbol"] = _clean_text(nse_data["Symbol"])
    nse_data["ISIN"] = _clean_text(nse_data["ISIN"])
    nse_data["Series"] = _clean_text(nse_data["Series"])

    constituent_missing_symbol = int(
        (
            sector_data["Symbol"].isna()
            | sector_data["Symbol"].eq("")
        ).sum()
    )

    sector_data = sector_data[
        sector_data["Symbol"].notna()
        & sector_data["Symbol"].ne("")
    ].copy()

    constituent_missing_isin = int(
        (
            sector_data["ISIN"].isna()
            | sector_data["ISIN"].eq("")
        ).sum()
    )

    nse_eq_data = nse_data[
        nse_data["Series"].eq("EQ").fillna(False)
    ].copy()

    nse_eq_rows = len(nse_eq_data)

    nse_eq_missing_symbol = int(
        (
            nse_eq_data["Symbol"].isna()
            | nse_eq_data["Symbol"].eq("")
        ).sum()
    )

    nse_eq_missing_isin = int(
        (
            nse_eq_data["ISIN"].isna()
            | nse_eq_data["ISIN"].eq("")
        ).sum()
    )

    nse_eq_data = nse_eq_data[
        nse_eq_data["Symbol"].notna()
        & nse_eq_data["Symbol"].ne("")
    ].copy()

    sector_duplicates = int(
        sector_data["Symbol"].duplicated(keep=False).sum()
    )

    nse_duplicates = int(
        nse_eq_data["Symbol"].duplicated(keep=False).sum()
    )

    nse_unique = nse_eq_data.drop_duplicates(
        subset=["Symbol"],
        keep=False,
    ).rename(columns={"ISIN": "NSE_ISIN"})

    audit = sector_data.merge(
        nse_unique[["Symbol", "NSE_ISIN"]],
        on="Symbol",
        how="left",
        validate="many_to_one",
    )

    symbol_matched = audit["Symbol"].isin(nse_unique["Symbol"])

    audit["NSE_EQ_Match"] = symbol_matched
    audit["ISIN_Status"] = "NSE_EQ_SYMBOL_MISSING"

    nse_isin_missing = (
        symbol_matched
        & (
            audit["NSE_ISIN"].isna()
            | audit["NSE_ISIN"].eq("")
        )
    )

    constituent_isin_missing = (
        symbol_matched
        & (
            audit["ISIN"].isna()
            | audit["ISIN"].eq("")
        )
    )

    both_isins = (
        symbol_matched
        & audit["ISIN"].notna()
        & audit["ISIN"].ne("")
        & audit["NSE_ISIN"].notna()
        & audit["NSE_ISIN"].ne("")
    )

    audit.loc[nse_isin_missing, "ISIN_Status"] = "NSE_ISIN_MISSING"
    audit.loc[
        constituent_isin_missing, "ISIN_Status"
    ] = "CONSTITUENT_ISIN_MISSING"

    audit.loc[
        both_isins & audit["ISIN"].eq(audit["NSE_ISIN"]),
        "ISIN_Status",
    ] = "MATCH"

    audit.loc[
        both_isins & audit["ISIN"].ne(audit["NSE_ISIN"]),
        "ISIN_Status",
    ] = "MISMATCH"

    audit["Audit_Status"] = "SYMBOL_MATCH_ISIN_MATCH"
    audit.loc[~symbol_matched, "Audit_Status"] = "NSE_EQ_SYMBOL_MISSING"
    audit.loc[nse_isin_missing, "Audit_Status"] = "NSE_ISIN_MISSING"
    audit.loc[
        constituent_isin_missing, "Audit_Status"
    ] = "CONSTITUENT_ISIN_MISSING"
    audit.loc[
        audit["ISIN_Status"].eq("MISMATCH"), "Audit_Status"
    ] = "ISIN_MISMATCH"

    ambiguous_symbols = set(
        nse_eq_data.loc[
            nse_eq_data["Symbol"].duplicated(keep=False),
            "Symbol",
        ].dropna()
    )

    ambiguous_mask = audit["Symbol"].isin(ambiguous_symbols)
    audit.loc[
        ambiguous_mask, "Audit_Status"
    ] = "NSE_EQ_SYMBOL_AMBIGUOUS"

    total = len(audit)
    matched = int(symbol_matched.sum())
    missing = total - matched

    isin_mismatch = int(audit["ISIN_Status"].eq("MISMATCH").sum())
    isin_match = int(audit["ISIN_Status"].eq("MATCH").sum())
    isin_missing = int(
        audit["ISIN_Status"].eq("CONSTITUENT_ISIN_MISSING").sum()
    )
    nse_isin_missing_rows = int(
        audit["ISIN_Status"].eq("NSE_ISIN_MISSING").sum()
    )

    source_status, source_name = _source_classification(nse_data)

    clean_primary_audit = (
        total > 0
        and source_status == "PRIMARY_MII"
        and missing == 0
        and isin_mismatch == 0
        and isin_missing == 0
        and nse_isin_missing_rows == 0
        and constituent_missing_symbol == 0
        and constituent_missing_isin == 0
        and nse_eq_missing_symbol == 0
        and nse_eq_missing_isin == 0
        and sector_duplicates == 0
        and nse_duplicates == 0
    )

    status = "PASS" if clean_primary_audit else "REVIEW"

    summary = {
        "sector": sector,
        "index": f"Nifty {sector}",
        "source": "NSE Indices Official Constituents",
        "nse_source": source_name,
        "nse_source_status": source_status,
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "raw_constituent_rows": raw_constituent_rows,
        "constituent_rows_audited": total,
        "constituent_rows_missing_symbol": constituent_missing_symbol,
        "constituent_rows_missing_isin": constituent_missing_isin,
        "nse_universe_rows_received": raw_nse_rows_received,
        "nse_eq_rows_before_symbol_validation": nse_eq_rows,
        "nse_eq_rows_missing_symbol": nse_eq_missing_symbol,
        "nse_eq_rows_missing_isin": nse_eq_missing_isin,
        "nse_eq_matched": matched,
        "nse_eq_missing": missing,
        "isin_matched": isin_match,
        "isin_mismatches": isin_mismatch,
        "constituent_isin_missing": isin_missing,
        "nse_isin_missing": nse_isin_missing_rows,
        "duplicate_constituent_symbol_rows": sector_duplicates,
        "duplicate_nse_eq_symbol_rows": nse_duplicates,
        "approved_for_sector_membership": status == "PASS",
    }

    return audit.sort_values("Symbol").reset_index(drop=True), summary
  
