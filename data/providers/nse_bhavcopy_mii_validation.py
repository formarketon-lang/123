
"""Reconcile NSE UDiFF Bhavcopy identity against dated NSE MII universe."""

from __future__ import annotations

import pandas as pd


class NSEMIIReconciliationError(ValueError):
    """Raised when Bhavcopy identity conflicts with NSE MII."""


def reconcile_bhavcopy_with_mii(
    bhavcopy: pd.DataFrame,
    universe: pd.DataFrame,
) -> dict:
    """Verify every observed Symbol + ISIN against the NSE MII snapshot.

    Missing universe observations and symbols absent from the dated MII
    snapshot are reported as REVIEW. Unknown rows are excluded from the
    verified observation set. A symbol/ISIN mismatch remains a hard failure.
    """

    if not isinstance(bhavcopy, pd.DataFrame) or bhavcopy.empty:
        raise NSEMIIReconciliationError("Bhavcopy is empty or invalid.")

    if not isinstance(universe, pd.DataFrame) or universe.empty:
        raise NSEMIIReconciliationError("NSE MII universe is empty or invalid.")

    required_bhavcopy = {"Date", "Symbol", "ISIN", "Series"}
    required_universe = {
        "Symbol", "ISIN", "Series", "Exchange", "Source",
        "Universe As Of Date", "Universe Verification Status",
    }

    missing_bhavcopy = required_bhavcopy.difference(bhavcopy.columns)
    missing_universe = required_universe.difference(universe.columns)

    if missing_bhavcopy:
        raise NSEMIIReconciliationError(
            "Bhavcopy missing fields: "
            + ", ".join(sorted(missing_bhavcopy))
        )

    if missing_universe:
        raise NSEMIIReconciliationError(
            "MII universe missing fields: "
            + ", ".join(sorted(missing_universe))
        )

    observed = bhavcopy.copy()
    verified = universe.copy()

    for frame, columns in (
        (observed, ["Symbol", "ISIN", "Series"]),
        (verified, ["Symbol", "ISIN", "Series", "Exchange", "Source",
                    "Universe Verification Status"]),
    ):
        for column in columns:
            frame[column] = (
                frame[column].astype("string").str.strip().str.upper()
            )

        if frame[columns].isna().any().any():
            raise NSEMIIReconciliationError(
                "Identity data contains missing values."
            )

        if frame[columns].eq("").any().any():
            raise NSEMIIReconciliationError(
                "Identity data contains blank values."
            )

    if not observed["Series"].eq("EQ").all():
        raise NSEMIIReconciliationError("Bhavcopy must contain EQ rows only.")

    if not verified["Series"].eq("EQ").all():
        raise NSEMIIReconciliationError("MII universe must contain EQ rows only.")

    if not verified["Exchange"].eq("NSE").all():
        raise NSEMIIReconciliationError("MII universe contains non-NSE rows.")

    if not verified["Source"].str.contains("MII", regex=False).all():
        raise NSEMIIReconciliationError("Official NSE MII source is required.")

    if not verified["Universe Verification Status"].eq("MII_DATED").all():
        raise NSEMIIReconciliationError("Every MII row must be MII_DATED.")

    for frame, label in ((observed, "Bhavcopy"), (verified, "MII universe")):
        if not frame["ISIN"].str.fullmatch(r"IN[A-Z0-9]{10}").all():
            raise NSEMIIReconciliationError(
                f"{label} contains invalid Indian ISIN."
            )

        if frame["Symbol"].duplicated().any():
            raise NSEMIIReconciliationError(
                f"{label} contains duplicate symbols."
            )

        if frame["ISIN"].duplicated().any():
            raise NSEMIIReconciliationError(
                f"{label} contains duplicate ISIN values."
            )

    observed_dates = pd.to_datetime(
        observed["Date"], errors="coerce"
    ).dt.normalize()

    if observed_dates.isna().any() or observed_dates.nunique() != 1:
        raise NSEMIIReconciliationError(
            "Bhavcopy must contain exactly one valid observation date."
        )

    observation_date = observed_dates.iloc[0]

    snapshot_dates = pd.to_datetime(
        verified["Universe As Of Date"], errors="coerce"
    ).dt.normalize()

    if snapshot_dates.isna().any():
        raise NSEMIIReconciliationError(
            "Every MII universe row must have a valid snapshot date."
        )

    if snapshot_dates.empty or snapshot_dates.nunique() != 1:
        raise NSEMIIReconciliationError(
            "MII universe must have one valid snapshot date."
        )

    snapshot_date = snapshot_dates.iloc[0]

    if snapshot_date != observation_date:
        raise NSEMIIReconciliationError(
            "MII snapshot date must exactly match Bhavcopy date."
        )

    mii_identity = verified.set_index("Symbol")["ISIN"].to_dict()
    observed_symbols = set(observed["Symbol"])
    mii_symbols = set(mii_identity)

    unknown_symbols = sorted(observed_symbols - mii_symbols)
    verified_symbols = observed_symbols.intersection(mii_symbols)

    isin_mismatch_symbols = sorted(
        symbol
        for symbol in verified_symbols
        if observed.loc[
            observed["Symbol"] == symbol, "ISIN"
        ].iloc[0] != mii_identity[symbol]
    )

    verified_symbols = verified_symbols.difference(
        isin_mismatch_symbols
    )
    exception_symbols = set(unknown_symbols).union(
        isin_mismatch_symbols
    )

    missing_symbols = sorted(mii_symbols - verified_symbols)
    verified_observations = observed[
        observed["Symbol"].isin(verified_symbols)
    ].copy()
    unverified_observations = observed[
        observed["Symbol"].isin(exception_symbols)
    ].copy()

    identity_exceptions = []
    for symbol in unknown_symbols:
        row = observed.loc[observed["Symbol"] == symbol].iloc[0]
        identity_exceptions.append({
            "symbol": symbol,
            "observed_isin": row["ISIN"],
            "mii_isin": None,
            "reason": "SYMBOL_NOT_IN_DATED_MII_UNIVERSE",
        })
    for symbol in isin_mismatch_symbols:
        row = observed.loc[observed["Symbol"] == symbol].iloc[0]
        identity_exceptions.append({
            "symbol": symbol,
            "observed_isin": row["ISIN"],
            "mii_isin": mii_identity[symbol],
            "reason": "SYMBOL_ISIN_MISMATCH",
        })

    coverage_pct = (
        len(verified_symbols) / len(mii_symbols)
    ) * 100.0

    identity_status = (
        "REVIEW"
        if unknown_symbols or isin_mismatch_symbols
        else "PASS"
    )
    coverage_status = (
        "PASS"
        if (
            not missing_symbols
            and not unknown_symbols
            and not isin_mismatch_symbols
        )
        else "REVIEW"
    )

    return {
        "observations": verified_observations.sort_values(
            "Symbol"
        ).reset_index(drop=True),
        "unverified_observations": unverified_observations.sort_values(
            "Symbol"
        ).reset_index(drop=True),
        "observation_date": observation_date.date().isoformat(),
        "mii_snapshot_date": snapshot_date.date().isoformat(),
        "observed_symbols": len(verified_symbols),
        "raw_observed_symbols": len(observed_symbols),
        "expected_symbols": len(mii_symbols),
        "unknown_symbols": unknown_symbols,
        "unknown_count": len(unknown_symbols),
        "isin_mismatch_symbols": isin_mismatch_symbols,
        "isin_mismatch_count": len(isin_mismatch_symbols),
        "identity_exceptions": identity_exceptions,
        "missing_symbols": missing_symbols,
        "missing_count": len(missing_symbols),
        "coverage_pct": round(coverage_pct, 4),
        "identity_status": identity_status,
        "coverage_status": coverage_status,
        "reconciliation_status": coverage_status,
    }
