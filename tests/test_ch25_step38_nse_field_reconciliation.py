
import pandas as pd
import pytest

from data.providers.nse_universe import (
    normalize_nse_mii_security_master,
)
from scripts.run_nse_universe_live_check import (
    compare_fields,
    prepare_raw_equity_scope,
)


def make_raw():
    return pd.DataFrame({
        "FININSTRMID": ["1", "2"],
        "TCKRSYMB": ["MARICO", "HINDUNILVR"],
        "FININSTRMNM": ["Marico Limited", "Hindustan Unilever Limited"],
        "SCTYSRS": ["EQ", "EQ"],
        "LISTGDT": ["0", "0"],
        "ISIN": ["INE196A01026", "INE030A01027"],
        "PARVAL": ["1", "1"],
        "ISSDCPTL": ["100", "200"],
        "DELFLG": ["N", "N"],
        "ELGBLTYNRMLMKT": ["1", "1"],
        "SCTYSTSNRMLMKT": ["1", "1"],
        "PRTDTOTRAD": ["0", "0"],
    })


def reconcile(raw, normalized):
    scoped, scope_summary = prepare_raw_equity_scope(raw)
    results, mismatches, coverage = compare_fields(
        scoped,
        normalized,
    )
    return results, mismatches, coverage, scope_summary


def test_exact_raw_to_normalized_mapping_passes():
    raw = make_raw()
    normalized = normalize_nse_mii_security_master(raw)

    results, mismatches, coverage, scope = reconcile(
        raw,
        normalized,
    )

    assert mismatches == 0
    assert coverage["status"] == "PASS"
    assert scope["eligible_eq_scope_rows"] == len(normalized)
    assert all(item["status"] == "PASS" for item in results.values())


def test_company_field_change_is_detected():
    raw = make_raw()
    normalized = normalize_nse_mii_security_master(raw)
    normalized.loc[0, "Company"] = "Incorrect Company"

    results, mismatches, coverage, _ = reconcile(
        raw,
        normalized,
    )

    assert mismatches == 1
    assert results["FININSTRMNM"]["status"] == "MISMATCH"


def test_missing_normalized_security_is_detected():
    raw = make_raw()
    normalized = normalize_nse_mii_security_master(raw)
    normalized = normalized.iloc[:1].copy()

    _, mismatches, coverage, _ = reconcile(raw, normalized)

    assert mismatches > 0
    assert coverage["status"] == "FAIL"
    assert coverage["missing_from_normalized_count"] == 1


def test_duplicate_raw_security_key_is_rejected():
    raw = make_raw()
    raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    normalized = normalize_nse_mii_security_master(raw)

    scoped, _ = prepare_raw_equity_scope(raw)

    with pytest.raises(ValueError, match="duplicate security keys"):
        compare_fields(scoped, normalized)
