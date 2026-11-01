
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.yahoo_adapter import fetch_yahoo_history


START_DATE = "2025-10-31"
END_DATE = "2026-10-29"

# NIFTY FMCG: Yahoo Finance verified ticker
INSTRUMENTS = [
    {
        "name": "NIFTY_FMCG",
        "symbol": "^CNXFMCG",
        "exchange": "NSE",
    }
]


def main():
    successful = []
    failed = []

    output_dir = PROJECT_ROOT / "data" / "raw" / "yahoo"
    output_dir.mkdir(parents=True, exist_ok=True)

    for instrument in INSTRUMENTS:
        name = instrument["name"]
        symbol = instrument["symbol"]
        exchange = instrument["exchange"]

        print(f"\nChecking: {name}")
        print(f"Yahoo ticker: {symbol}")

        try:
            df = fetch_yahoo_history(
                symbol=symbol,
                start_date=START_DATE,
                end_date=END_DATE,
                interval="1d",
                exchange=exchange,
            )

            if df.empty:
                raise ValueError("Downloaded dataset is empty.")

            file_path = output_dir / f"{name}_yahoo.csv"
            df.to_csv(file_path, index=False)

            result = {
                "name": name,
                "symbol": symbol,
                "rows": len(df),
                "first_date": str(df["Date"].min().date()),
                "last_date": str(df["Date"].max().date()),
                "columns": list(df.columns),
                "file": str(file_path),
            }

            successful.append(result)
            print("PASS:", result)

        except Exception as exc:
            error_result = {
                "name": name,
                "symbol": symbol,
                "error": str(exc),
            }

            failed.append(error_result)
            print("FAIL:", error_result)

    print("\n========== NIFTY FMCG YAHOO CHECK ==========")
    print("Successful:", len(successful))
    print("Failed:", len(failed))

    if failed:
        print("Failures:", failed)
        raise SystemExit(1)

    print("\nAll NIFTY FMCG checks completed successfully.")


if __name__ == "__main__":
    main()
