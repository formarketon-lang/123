"""
TradeLab Pro - Central Stock Universe

NSE MII is the primary verified NSE cash-equity universe.
Sector membership is independently maintained and validated.
"""

from data.providers.nse_universe import fetch_nse_equity_universe


# Only independently verified sector membership belongs here.
# NSE security master does not establish sector membership.
SECTOR_UNIVERSE = {
    "FMCG": [
        "HINDUNILVR",
    ],
}


def load_nse_universe():
    """Fetch and normalize the official NSE EQ security universe."""
    return fetch_nse_equity_universe()


def get_sector_symbols(sector):
    """Return configured symbols for a sector."""
    if not isinstance(sector, str):
        return []

    return list(SECTOR_UNIVERSE.get(sector, []))


def get_available_sectors():
    """Return sectors with configured stock lists."""
    return sorted(SECTOR_UNIVERSE.keys())


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


def validate_sector_membership(sector, symbols):
    """
    Allow sector comparison only when every selected symbol
    belongs to the independently configured sector universe.
    """

    if not isinstance(sector, str) or not sector.strip():
        return False, "No valid sector selected."

    configured_symbols = {
        symbol.strip().upper()
        for symbol in get_sector_symbols(sector)
    }

    requested_symbols = {
        str(symbol).strip().upper()
        for symbol in symbols
        if str(symbol).strip()
    }

    if not configured_symbols:
        return False, (
            f"No verified stock membership list exists for {sector}."
        )

    if not requested_symbols:
        return False, "No stocks selected for sector validation."

    unverified = sorted(requested_symbols - configured_symbols)

    if unverified:
        return False, (
            "Sector membership is not verified for: "
            + ", ".join(unverified)
        )

    return True, "All selected stocks have configured sector membership."
    
