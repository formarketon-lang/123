
"""
TradeLab Pro - Benchmark Mapping

Main index symbols and verified sector index mappings.
Unverified sector mappings must remain unavailable.
"""

MAIN_BENCHMARKS = {
    "Nifty 50": "^NSEI",
    "Nifty Next 50": "^NSMIDCP",
    "Nifty 100": "^CNX100",
    "Nifty 200": "^CNX200",
    "Nifty 500": "^CRSLDX",
}

# Add sector mappings only after verification.
SECTOR_BENCHMARKS = {
    "FMCG": "^CNXFMCG",
}


def get_main_benchmarks():
    """Return configured main benchmark indices."""
    return dict(MAIN_BENCHMARKS)


def get_sector_benchmark(sector):
    """Return a verified sector benchmark, or None."""
    if not isinstance(sector, str):
        return None

    return SECTOR_BENCHMARKS.get(sector)


def get_available_sector_mappings():
    """Return only sectors with configured benchmark mappings."""
    return dict(SECTOR_BENCHMARKS)
  
