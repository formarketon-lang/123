from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.yahoo_adapter import fetch_yahoo_history


END_DATE = "2026-10-29"

INSTRUMENTS = [
    {
        "name": "MARICO",
        "symbol": "MARICO.NS",
        "exchange": "NSE",
        "start_date": "2025-10-31",
    },
    {
        "name": "NIFTY_50",
        "symbol": "^NSEI",
        "exchange": "NSE",
        "start_date": "2025-10-30",
    },
    {
        "name": "NIFTY_FMCG",
        "symbol": "^CNXFMCG",
        "exchange": "NSE",
        "start_date": "2025-10-30",
    },
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
        start_date = instrument["start_date"]

        print(f"\nChecking: {name}")
        print(f"Yahoo ticker: {symbol}")
        print(f"Date range: {start_date} to {END_DATE}")

        try:
            df = fetch_yahoo_history(
                symbol=symbol,
                start_date=start_date,
                end_date=END_DATE,
                interval="1d",
                exchange=exchange,
            )

            if df.empty:
                raise ValueError("Downloaded dataset is empty.")

            required_columns = [
                "Date",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]

            missing = [
                column for column in required_columns
                if column not in df.columns
            ]

            if missing:
                raise ValueError(
                    f"Required columns missing: {missing}"
                )

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

    print("\n========== COMBINED YAHOO CHECK ==========")
    print("Successful:", len(successful))
    print("Failed:", len(failed))

    print("\nSuccessful instruments:")
    for item in successful:
        print(item)

    if failed:
        print("\nFailures:")
        for item in failed:
            print(item)

        raise SystemExit(1)

    print("\nALL THREE YAHOO CHECKS PASSED.")


if __name__ == "__main__":
    main()