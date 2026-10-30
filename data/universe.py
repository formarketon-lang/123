
"""
TradeLab Pro - Stock Universe

Stores the currently configured stock lists by sector.
Only verified/configured symbols should be added here.
"""

SECTOR_UNIVERSE = {
    "FMCG": [
        "HINDUNILVR",
    ],
}


def get_sector_symbols(sector):
    """
    Return the configured stock symbols for a sector.

    Returns an empty list when no universe is configured.
    """

    if not isinstance(sector, str):
        return []

    return list(SECTOR_UNIVERSE.get(sector, []))


def get_available_sectors():
    """Return sectors with a configured stock universe."""

    return sorted(SECTOR_UNIVERSE.keys())
  
