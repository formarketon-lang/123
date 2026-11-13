
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

    Missing universe observations are reported as REVIEW, not fabricated.
    Unknown symbols, mismatched ISINs and invalid universe identities fail.
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
    ).dropna().dt.normalize()

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

    if unknown_symbols:
        raise NSEMIIReconciliationError(
            "Bhavcopy symbols absent from MII: "
            + ", ".join(unknown_symbols)
        )

    mismatches = sorted(
        symbol
        for symbol in observed_symbols
        if observed.loc[
            observed["Symbol"] == symbol, "ISIN"
        ].iloc[0] != mii_identity[symbol]
    )

    if mismatches:
        raise NSEMIIReconciliationError(
            "Symbol/ISIN mismatch against MII: "
            + ", ".join(mismatches)
        )

    missing_symbols = sorted(mii_symbols - observed_symbols)

    coverage_pct = (
        len(observed_symbols) / len(mii_symbols)
    ) * 100.0

    return {
        "observations": observed.sort_values("Symbol").reset_index(drop=True),
        "observation_date": observation_date.date().isoformat(),
        "mii_snapshot_date": snapshot_date.date().isoformat(),
        "observed_symbols": len(observed_symbols),
        "expected_symbols": len(mii_symbols),
        "missing_symbols": missing_symbols,
        "missing_count": len(missing_symbols),
        "coverage_pct": round(coverage_pct, 4),
        "identity_status": "PASS",
        "coverage_status": "PASS" if not missing_symbols else "REVIEW",
        "reconciliation_status": "PASS" if not missing_symbols else "REVIEW",
    }
