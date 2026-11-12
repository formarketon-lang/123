
import pandas as pd
import pytest

from scripts.run_ch25_step39_nse_identity_continuity import (
    build_identity_ledger,
)


def make_frame():
    return pd.DataFrame({
        "Symbol": ["AAA", "BBB"],
        "Series": ["EQ", "EQ"],
        "ISIN": ["INE000A01011", "INE000B01011"],
    })


def test_unchanged_identity_passes():
    frame = make_frame()
    result = build_identity_ledger(frame, frame.copy())

    assert result["status"] == "PASS"
    assert result["unchanged_identity_count"] == 2
    assert result["change_event_count"] == 0
    assert result["review_required"] is False


def test_symbol_change_same_isin_is_recorded():
    old = make_frame()
    new = old.copy()
    new.loc[0, "Symbol"] = "AAA_NEW"

    result = build_identity_ledger(old, new)

    assert result["status"] == "PASS"
    assert result["review_required"] is True
    assert result["events"][0]["event_type"] == (
        "SAME_ISIN_IDENTITY_CHANGE"
    )


def test_isin_change_same_symbol_is_recorded():
    old = make_frame()
    new = old.copy()
    new.loc[0, "ISIN"] = "INE000C01011"

    result = build_identity_ledger(old, new)

    assert result["change_event_count"] == 1
    assert result["events"][0]["event_type"] == (
        "ISIN_CHANGED_SAME_SYMBOL"
    )


def test_addition_and_removal_are_recorded():
    old = make_frame()
    new = pd.DataFrame({
        "Symbol": ["BBB", "CCC"],
        "Series": ["EQ", "EQ"],
        "ISIN": ["INE000B01011", "INE000C01011"],
    })

    result = build_identity_ledger(old, new)
    event_types = {item["event_type"] for item in result["events"]}

    assert "REMOVED_SECURITY" in event_types
    assert "ADDED_SECURITY" in event_types


def test_duplicate_isin_is_rejected():
    old = make_frame()
    new = make_frame()
    new.loc[1, "ISIN"] = new.loc[0, "ISIN"]

    with pytest.raises(ValueError, match="duplicate ISIN"):
        build_identity_ledger(old, new)


def test_invalid_isin_is_rejected():
    old = make_frame()
    new = make_frame()
    new.loc[0, "ISIN"] = "INVALID"

    with pytest.raises(ValueError, match="invalid ISIN"):
        build_identity_ledger(old, new)
      
