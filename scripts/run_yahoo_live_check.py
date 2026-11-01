
from pathlib import Path
import sys

# Add project root to Python import path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.yahoo_adapter import fetch_yahoo_history


START_DATE = "2025-10-31"
END_DATE = "2026-10-29"

# First verification: NSE equity only
INSTRUMENTS = ["MARICO"]


def main():
    successful = []
    failed = []

    output_dir = PROJECT_ROOT / "data" / "raw" / "yahoo"
    output_dir.mkdir(parents=True, exist_ok=True)

    for symbol in INSTRUMENTS:
        print(f"\nChecking Yahoo data: {symbol}")

        try:
            df = fetch_yahoo_history(
                symbol=symbol,
                start_date=START_DATE,
                end_date=END_DATE,
                interval="1d",
                exchange="NSE",
            )

            if df.empty:
                raise ValueError("Downloaded dataset is empty.")

            file_path = output_dir / f"{symbol}_yahoo.csv"
            df.to_csv(file_path, index=False)

            result = {
                "symbol": symbol,
                "rows": len(df),
                "first_date": str(df["Date"].min().date()),
                "last_date": str(df["Date"].max().date()),
                "file": str(file_path),
            }

            successful.append(result)
            print("PASS:", result)

        except Exception as exc:
            failed.append({
                "symbol": symbol,
                "error": str(exc),
            })
            print("FAIL:", symbol, str(exc))

    print("\n========== YAHOO LIVE CHECK ==========")
    print("Successful:", len(successful))
    print("Failed:", len(failed))

    if failed:
        print("Failures:", failed)
        raise SystemExit(1)

    print("\nAll Yahoo downloads completed successfully.")


if __name__ == "__main__":
    main()
