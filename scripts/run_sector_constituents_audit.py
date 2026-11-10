
"""Live audit of Nifty FMCG constituents against NSE MII EQ universe."""

import json
from pathlib import Path

from data.constituent_audit import (
    SECTOR,
    build_constituent_audit,
)
from data.providers.nifty_constituents import fetch_sector_constituents
from data.providers.nse_universe import fetch_nse_equity_universe


REPORT_DIR = Path("reports/sector_constituents")


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print(
        "Downloading official Nifty FMCG constituents "
        "(raw duplicates kept)..."
    )

    constituents = fetch_sector_constituents(
        SECTOR,
        deduplicate=False,
    )

    print("Raw constituent rows:", len(constituents))

    print("Downloading NSE MII EQ universe...")

    nse_universe = fetch_nse_equity_universe()

    print("NSE universe rows:", len(nse_universe))

    detail, summary = build_constituent_audit(
        constituents,
        nse_universe,
        SECTOR,
    )

    detail_path = (
        REPORT_DIR / "fmcg_constituents_vs_nse_eq.csv"
    )

    summary_path = (
        REPORT_DIR / "fmcg_constituents_audit.json"
    )

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

    if summary["status"] != "PASS":
        raise SystemExit(
            "Constituent audit requires REVIEW; "
            "membership is not approved."
        )


if __name__ == "__main__":
    main()
    
