
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.providers.nse_universe import (
    NSE_MII_SECURITY_URL_TEMPLATE,
    fetch_nse_equity_universe,
)

REPORT_DIR = PROJECT_ROOT / "reports" / "nse_universe_live"


class AuditedSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.requested_urls = []

    def get(self, url, *args, **kwargs):
        self.requested_urls.append(url)
        return super().get(url, *args, **kwargs)


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    audit_time = datetime.now(timezone.utc)
    audit_id = audit_time.strftime("%Y%m%d_%H%M%S")

    session = AuditedSession()

    print("========== NSE MII LIVE VERIFICATION ==========")

    try:
        universe = fetch_nse_equity_universe(
            timeout=45,
            session=session,
            lookback_days=7,
        )

        mii_urls = [
            url for url in session.requested_urls
            if "/content/cm/NSE_CM_security_" in url
        ]

        print("\nRequested MII URLs:")
        for url in mii_urls:
            print(url)

        sources = universe["Source"].dropna().unique().tolist()

        if sources != ["NSE MII Security Master"]:
            raise ValueError(
                f"MII was not confirmed as source: {sources}"
            )

        if universe.empty:
            raise ValueError("NSE universe is empty.")

        required = [
            "Symbol",
            "Company",
            "Series",
            "ISIN",
            "Delete Flag",
            "Normal Market Eligibility",
            "Normal Market Status",
            "Source",
        ]

        missing = [
            column for column in required
            if column not in universe.columns
        ]

        if missing:
            raise ValueError(
                f"Required columns missing: {missing}"
            )

        if not (universe["Series"] == "EQ").all():
            raise ValueError("Non-EQ security found.")

        if not (universe["Delete Flag"] == "N").all():
            raise ValueError("Deleted security found.")

        if not (
            universe["Normal Market Eligibility"] == "1"
        ).all():
            raise ValueError("Ineligible security found.")

        if (
            universe["Normal Market Status"] == "3"
        ).any():
            raise ValueError("Suspended security found.")

        if universe["Symbol"].str.endswith("$").any():
            raise ValueError("BSE-exclusive symbol found.")

        if not universe["ISIN"].str.fullmatch(
            r"IN[A-Z0-9]{10}",
            na=False,
        ).all():
            raise ValueError("Invalid ISIN found.")

        if universe.duplicated(
            subset=["Symbol", "Series", "ISIN"]
        ).any():
            raise ValueError("Duplicate security found.")

        if "Permitted to Trade" in universe.columns:
            if (
                universe["Permitted to Trade"] == "2"
            ).any():
                raise ValueError(
                    "BSE-exclusive PrtdToTrad=2 security found."
                )

        if "MARICO" not in set(universe["Symbol"]):
            raise ValueError(
                "MARICO was not found in the live universe."
            )

        csv_path = REPORT_DIR / f"nse_universe_{audit_id}.csv"
        json_path = REPORT_DIR / f"nse_universe_{audit_id}.json"

        universe.to_csv(csv_path, index=False)

        summary = {
            "audit_id": audit_id,
            "audit_time_utc": audit_time.isoformat(),
            "source": sources,
            "mii_urls_attempted": mii_urls,
            "total_eligible_eq_securities": len(universe),
            "unique_symbols": int(universe["Symbol"].nunique()),
            "marico_found": True,
            "series_counts": (
                universe["Series"].value_counts().to_dict()
            ),
            "permitted_to_trade_counts": (
                universe["Permitted to Trade"]
                .value_counts(dropna=False)
                .to_dict()
                if "Permitted to Trade" in universe.columns
                else {}
            ),
            "columns": universe.columns.tolist(),
            "csv_file": str(csv_path),
            "status": "PASS",
        }

        with open(json_path, "w", encoding="utf-8") as file:
            json.dump(
                summary,
                file,
                indent=2,
                default=str,
            )

        print("\n========== LIVE AUDIT SUMMARY ==========")
        print(json.dumps(summary, indent=2, default=str))
        print("\nNSE MII LIVE VERIFICATION: PASS")

    except Exception as error:
        print("\nNSE MII LIVE VERIFICATION: FAIL")
        print(f"{type(error).__name__}: {error}")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
