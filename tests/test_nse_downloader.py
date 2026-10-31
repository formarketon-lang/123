
from data.providers.nse_downloader import (
    create_nse_session,
    download_equity_history,
    save_nse_csv,
)


def test_nse_downloader_imports():
    assert callable(create_nse_session)
    assert callable(download_equity_history)
    assert callable(save_nse_csv)
  

import pytest


def test_invalid_date_format():
    with pytest.raises(ValueError):
        download_equity_history(
            "MARICO",
            "31-10-2025",
            "29-10-2026",
        )


def test_start_date_after_end_date():
    with pytest.raises(ValueError):
        download_equity_history(
            "MARICO",
            "2026-10-29",
            "2025-10-31",
        )
        
