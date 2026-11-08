from __future__ import annotations

import zipfile

import pandas as pd

from data.providers.exchange_universe_reconciliation import (
    build_exchange_universe_reconciliation,
    load_bse_equity_universe,
    load_nse_cm_diagnostic,
    load_nse_equity_universe,
    validate_metadata,
)


def nse_data():
    return pd.DataFrame({
        "Symbol": ["MARICO", "HINDUNILVR"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "Company": [
            "Marico Limited",
            "Hindustan Unilever Limited",
        ],
    })


def bse_data():
    return nse_data().copy()


def metadata(exchange):
    return {
        "exchange": exchange,
        "source_url": "https://example.com/security-master.csv",
        "filename": f"{exchange}.csv",
        "downloaded_at_utc": "2026-11-08T10:00:00+00:00",
        "trading_date": "2026-11-06",
        "sha256": "a" * 64,
    }


def run(nse=None, bse=None, nm=None, bm=None):
    return build_exchange_universe_reconciliation(
        nse if nse is not None else nse_data(),
        bse if bse is not None else bse_data(),
        nm if nm is not None else metadata("NSE"),
        bm if bm is not None else metadata("BSE"),
    )


def test_separate_exchange_universes_pass():
    detail, summary = run()

    assert summary["status"] == "PASS"
    assert summary["exchange_universes_kept_separate"] is True
    assert len(detail) == 4


def test_cross_listed_isins_are_reported():
    _, summary = run()

    assert summary["cross_listed_isin_count"] == 2
    assert "INE196A01026" in summary["cross_listed_isins"]


def test_duplicate_nse_isin_fails():
    nse = nse_data()
    duplicate = nse.iloc[[0]].copy()
    duplicate["Symbol"] = "MARICO2"

    _, summary = run(
        nse=pd.concat([nse, duplicate], ignore_index=True)
    )

    assert summary["nse"]["duplicate_isin_rows"] == 2
    assert summary["status"] == "REVIEW"


def test_duplicate_bse_symbol_fails():
    bse = bse_data()
    duplicate = bse.iloc[[0]].copy()
    duplicate["ISIN"] = "INE999A01099"

    _, summary = run(
        bse=pd.concat([bse, duplicate], ignore_index=True)
    )

    assert summary["bse"]["duplicate_symbol_rows"] == 2
    assert summary["status"] == "REVIEW"


def test_invalid_isin_fails():
    nse = nse_data()
    nse.loc[0, "ISIN"] = "INVALID"

    _, summary = run(nse=nse)

    assert summary["nse"]["invalid_isin_rows"] == 1
    assert summary["status"] == "REVIEW"


def test_missing_company_fails():
    bse = bse_data()
    bse.loc[0, "Company"] = None

    _, summary = run(bse=bse)

    assert summary["bse"]["missing_identity_rows"] == 1
    assert summary["status"] == "REVIEW"


def test_invalid_source_metadata_fails():
    bad = metadata("NSE")
    bad["sha256"] = "invalid"

    assert validate_metadata(bad, "NSE") is False

    _, summary = run(nm=bad)

    assert summary["status"] == "REVIEW"


def test_wrong_exchange_metadata_fails():
    assert validate_metadata(metadata("BSE"), "NSE") is False


def test_missing_snapshot_columns_rejected():
    try:
        run(nse=nse_data().drop(columns=["ISIN"]))
    except ValueError as exc:
        assert "ISIN" in str(exc)
    else:
        raise AssertionError("Missing ISIN column was accepted")


def test_sector_mapping_never_activates():
    _, summary = run()

    assert summary["mapping_eligible"] is False
    assert summary["sector_mapping_activated"] is False
    assert summary["classification_inferred"] is False


def test_nse_equity_loader_filters_eq_series(tmp_path):
    path = tmp_path / "EQUITY_L.csv"

    pd.DataFrame({
        "SYMBOL": ["AAA", "BBB"],
        "NAME OF COMPANY": ["AAA Ltd", "BBB Ltd"],
        " SERIES": ["EQ", "BE"],
        " ISIN NUMBER": ["INE123A01011", "INE123A01012"],
    }).to_csv(path, index=False)

    result, diag = load_nse_equity_universe(path)

    assert result["Symbol"].tolist() == ["AAA"]
    assert diag["excluded_non_eq_rows"] == 1


def test_bse_zip_loader_filters_active_eq(tmp_path):
    path = tmp_path / "scrip.zip"

    source = pd.DataFrame({
        "TckrSymb": ["AAA", "BBB", "CCC"],
        "FinInstrmNm": ["AAA Ltd", "BBB Ltd", "CCC Ltd"],
        "ISIN": [
            "INE123A01011",
            "INE123A01012",
            "INE123A01013",
        ],
        "FinInstrmTp": ["E", "E", "D"],
        "SctyTpFlg": ["EQ", "EQ", "EQ"],
        "Sts": ["A", "S", "A"],
        "UnqPdctIdr": ["1-1", "1-2", "1-3"],
    })

    csv_bytes = source.to_csv(index=False).encode()

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "SCRIP/BSE_EQ_SCRIP_TEST.csv",
            csv_bytes,
        )

    result, diag = load_bse_equity_universe(path)

    assert result["Symbol"].tolist() == ["AAA"]
    assert diag["selected_active_eq_rows"] == 1


def test_nse_cm_loader_is_diagnostic_and_filters_active_eq(tmp_path):
    path = tmp_path / "nse.csv.gz"

    source = pd.DataFrame({
        "TckrSymb": ["AAA", "BBB", "CCC"],
        "FinInstrmNm": ["AAA Ltd", "BBB Ltd", "CCC Ltd"],
        "ISIN": [
            "INE123A01011",
            "INE123A01012",
            "INE123A01013",
        ],
        "SctySrs": ["EQ", "EQ", "BE"],
        "DelFlg": ["N", "Y", "N"],
    })

    source.to_csv(path, index=False, compression="gzip")

    result, diag = load_nse_cm_diagnostic(path)

    assert result["Symbol"].tolist() == ["AAA"]
    assert diag["not_used_as_primary_listed_universe"] is True