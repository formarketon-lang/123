"""
TradeLab Pro - Central Stock Universe

NSE MII is the primary verified NSE cash-equity universe.
Sector membership is loaded from official Nifty Indices data
and approved only after a successful NSE MII Symbol/ISIN audit.
"""

from data.providers.nse_universe import fetch_nse_equity_universe
from data.providers.nifty_constituents import (
    SECTOR_CONSTITUENT_URLS,
    fetch_sector_constituents,
)
from data.constituent_audit import build_constituent_audit


def load_nse_universe():
    """Fetch and normalize the official NSE EQ security universe."""
    return fetch_nse_equity_universe()


def get_sector_symbols(sector, universe=None):
    """
    Return sector symbols only after a successful live audit.

    No hardcoded or unverified sector membership is permitted.
    """
    if not isinstance(sector, str):
        return []

    sector = sector.strip().upper()

    if not sector or sector not in SECTOR_CONSTITUENT_URLS:
        return []

    constituents = fetch_sector_constituents(
        sector,
        deduplicate=False,
    )

    nse_universe = (
        universe
        if universe is not None
        else load_nse_universe()
    )

    _, summary = build_constituent_audit(
        constituents,
        nse_universe,
        sector=sector,
    )

    if (
        summary.get("status") != "PASS"
        or summary.get("approved_for_sector_membership") is not True
    ):
        raise ValueError(
            f"{sector} membership audit failed: "
            f"{summary.get('status', 'UNKNOWN')}. "
            "Sector comparison is blocked."
        )

    symbols = (
        constituents["Symbol"]
        .dropna()
        .astype("string")
        .str.strip()
        .str.upper()
    )

    return sorted(
        symbol
        for symbol in symbols.unique().tolist()
        if symbol
    )


def get_available_sectors():
    """Return only sectors with an official constituent source."""
    return sorted(SECTOR_CONSTITUENT_URLS.keys())


def validate_symbols_against_universe(symbols, universe):
    """Validate symbols against the verified NSE EQ universe."""

    if universe is None or universe.empty:
        raise ValueError("Verified NSE stock universe is empty.")

    required = {"Symbol", "ISIN", "Series"}
    missing = required.difference(universe.columns)

    if missing:
        raise ValueError(
            "NSE universe missing required columns: "
            + ", ".join(sorted(missing))
        )

    eligible = universe[
        (universe["Series"].astype("string").str.upper() == "EQ")
        & universe["ISIN"].notna()
    ]

    available = set(
        eligible["Symbol"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    requested = list(dict.fromkeys(
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    ))

    unknown = sorted(set(requested) - available)

    if unknown:
        raise ValueError(
            "Symbols not found in verified NSE EQ universe: "
            + ", ".join(unknown)
        )

    return requested


def validate_sector_membership(sector, symbols, universe=None):
    """
    Allow sector comparison only after official constituent
    data passes the NSE MII Symbol/ISIN audit.
    """

    if not isinstance(sector, str) or not sector.strip():
        return False, "No valid sector selected."

    requested_symbols = {
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    }

    if not requested_symbols:
        return False, "No stocks selected for sector validation."

    try:
        verified_symbols = set(
            get_sector_symbols(sector, universe=universe)
        )
    except Exception as error:
        return False, (
            f"Official {sector} membership verification failed: "
            f"{error}"
        )

    if not verified_symbols:
        return False, (
            f"No verified stock membership list exists for {sector}."
        )

    unverified = sorted(requested_symbols - verified_symbols)

    if unverified:
        return False, (
            "Sector membership is not verified for: "
            + ", ".join(unverified)
        )

    return True, (
        "All selected stocks passed official sector membership audit."
    )
    
