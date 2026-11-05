
import pytest

from data import universe


@pytest.fixture
def verified_fmcg_membership(monkeypatch):
    """Provide deterministic audited membership for unit tests."""
    def fake_get_sector_symbols(sector, universe=None):
        if str(sector).strip().upper() == "FMCG":
            return ["HINDUNILVR"]
        return []

    monkeypatch.setattr(
        universe,
        "get_sector_symbols",
        fake_get_sector_symbols,
    )


def test_verified_fmcg_member_is_allowed(verified_fmcg_membership):
    allowed, reason = universe.validate_sector_membership(
        "FMCG",
        ["HINDUNILVR"],
    )

    assert allowed is True
    assert "membership" in reason.lower()


def test_unverified_stock_is_blocked_from_sector_comparison(
    verified_fmcg_membership,
):
    allowed, reason = universe.validate_sector_membership(
        "FMCG",
        ["MARICO"],
    )

    assert allowed is False
    assert "MARICO" in reason


def test_mixed_verified_and_unverified_stocks_are_blocked(
    verified_fmcg_membership,
):
    allowed, reason = universe.validate_sector_membership(
        "FMCG",
        ["HINDUNILVR", "MARICO"],
    )

    assert allowed is False
    assert "MARICO" in reason


def test_unknown_sector_is_blocked(verified_fmcg_membership):
    allowed, reason = universe.validate_sector_membership(
        "UNKNOWN SECTOR",
        ["HINDUNILVR"],
    )

    assert allowed is False
    assert "No verified" in reason


def test_empty_stock_selection_is_blocked(verified_fmcg_membership):
    allowed, reason = universe.validate_sector_membership(
        "FMCG",
        [],
    )

    assert allowed is False
    assert "No stocks" in reason


def test_sector_membership_is_case_insensitive(
    verified_fmcg_membership,
):
    allowed, reason = universe.validate_sector_membership(
        "FMCG",
        ["hindunilvr"],
    )

    assert allowed is True
