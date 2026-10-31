
import sys
from pathlib import Path

# Make project root available for imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.providers.nse_downloader import (
    download_equity_history,
    save_nse_csv,
)
from data.providers.nse_index_downloader import (
    download_index_history,
    save_nse_index_csv,
)


START_DATE = "2025-10-31"
END_DATE = "2026-10-29"


def run_check(name, download_function, save_function):
    print(f"\nChecking: {name}")

    try:
        df = download_function(
            name,
            START_DATE,
            END_DATE,
        )

        if df.empty:
            raise ValueError("Downloaded dataset is empty.")

        required = ["Date", "Open", "High", "Low", "Close"]

        missing = [
            column for column in required
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Required columns missing: {missing}"
            )

        saved_path = save_function(df, name)

        print("STATUS: PASS")
        print(f"Rows: {len(df)}")
        print(f"First date: {df['Date'].min()}")
        print(f"Last date: {df['Date'].max()}")
        print(f"Saved: {saved_path}")

        return True

    except Exception as error:
        print("STATUS: FAIL")
        print(f"Reason: {type(error).__name__}: {error}")
        return False


def main():
    results = {}

    results["MARICO"] = run_check(
        "MARICO",
        download_equity_history,
        save_nse_csv,
    )

    results["NIFTY 50"] = run_check(
        "NIFTY 50",
        download_index_history,
        save_nse_index_csv,
    )

    results["NIFTY FMCG"] = run_check(
        "NIFTY FMCG",
        download_index_history,
        save_nse_index_csv,
    )

    print("\n========== NSE LIVE CHECK SUMMARY ==========")

    for name, passed in results.items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")

    passed_count = sum(results.values())
    print(f"Total Passed: {passed_count}/3")

    if passed_count != 3:
        print("NSE LIVE CHECK: INCOMPLETE")
        sys.exit(1)

    print("NSE LIVE CHECK: ALL PASSED")


if __name__ == "__main__":
    main()
  
