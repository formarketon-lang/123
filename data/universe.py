"""
TradeLab Pro - Central Stock Universe

NSE MII is the primary verified NSE cash-equity universe.
Sector membership is kept separate and must be independently verified.
"""

from data.providers.nse_universe import fetch_nse_equity_universe


# Only independently configured sector symbols belong here.
# Do not infer sector membership from the NSE security master.
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
    """
    Keep only symbols that exist in the verified NSE universe.
    Raise an error for unknown symbols instead of silently accepting them.
    """
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